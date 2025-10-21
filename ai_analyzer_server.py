import os
import json
from typing import Optional, List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr
from openai import OpenAI

# ---------- Config ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY env var.")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- FastAPI ----------
app = FastAPI(
    title="AI Analyzer Server",
    version="1.0.0",
    description="Simple, stable FastAPI wrapper using OpenAI Responses API (OpenAI() client).",
)

# CORS (adjust origins for production if you want)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Models ----------
Timeframe = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"]

class AnalyzeRequest(BaseModel):
    ticker: constr(strip_whitespace=True, min_length=1) = Field(..., description="Ticker symbol, e.g., NVDA")
    timeframe: Timeframe = Field("6mo", description="Historical window for context (not fetched here)")
    dsl: Optional[str] = Field(None, description="Optional strategy DSL to evaluate")
    notes: Optional[str] = Field(None, description="Free-text hints/context you want the model to consider")


class AnalyzerSignal(BaseModel):
    name: str
    description: str
    verdict: Literal["buy", "hold", "sell", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)


class AnalyzeResponse(BaseModel):
    name: str
    sector: Optional[str] = None
    composite_score: float = Field(ge=0, le=100, description="0-100")
    pe_ratio: Optional[float] = None
    market_cap_billions: Optional[float] = None
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None

    last_analyzed: str
    summary: str

    # DSL
    dsl_signals: Optional[List[AnalyzerSignal]] = None
    dsl_error: Optional[str] = None

    # Render-friendly blobs
    chart_base64: Optional[str] = None  # Keep field for compatibility (can be filled elsewhere)


# ---------- Helpers ----------
def build_json_schema_for_response():
    """
    Use OpenAI Responses JSON schema to enforce a clean shape from the model.
    """
    # Convert our Pydantic schema to JSON Schema
    schema = AnalyzeResponse.model_json_schema()
    # OpenAI requires a top-level "name" and "schema" with "strict": True preferred
    return {
        "name": "analyze_response",
        "strict": True,
        "schema": schema,
    }


SYSTEM_PROMPT = """You are a precise, cautious financial analysis assistant.
- ALWAYS return valid JSON that matches the provided JSON schema.
- If you are not certain about real-time numeric values (price, volume, market cap), leave them null.
- You do NOT fetch live data; focus on qualitative analysis, risk factors, catalysts, competition, moat, and valuation frameworks.
- If a DSL strategy is provided, interpret it sensibly and emit structured 'dsl_signals' (or a concise 'dsl_error').
- Be conservative: do not hallucinate exact numbers.
- Keep the 'summary' factual, concise, and helpful for an investor.
"""


def build_user_prompt(req: AnalyzeRequest) -> str:
    lines = [
        f"Ticker: {req.ticker}",
        f"Timeframe: {req.timeframe}",
        f"DSL: {req.dsl or '(none)'}",
    ]
    if req.notes:
        lines.append(f"Notes: {req.notes}")
    lines.append(
        "\nReturn ONLY the JSON object as per schema. If a field is unknown, use null. "
        "Do not invent exact prices or volumes."
    )
    return "\n".join(lines)


# ---------- Routes ----------
@app.get("/", tags=["meta"])
def index():
    return {
        "name": "AI Analyzer Server",
        "status": "ok",
        "endpoints": {
            "POST /analyze": {
                "body": {
                    "ticker": "NVDA",
                    "timeframe": "6mo",
                    "dsl": "SMA(10) cross SMA(50) and RSI<70",
                    "notes": "Focus on AI catalysts."
                }
            },
            "GET /healthz": {}
        },
        "notes": "Call POST /analyze. GET on /analyze will return 405 (Method Not Allowed).",
        "sdk": "OpenAI Responses API via OpenAI() client",
        "model": MODEL_NAME,
    }


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
def analyze(req: AnalyzeRequest):
    """
    Main analysis endpoint.
    Uses OpenAI Responses API with JSON Schema to guarantee clean JSON output.
    """
    try:
        schema = build_json_schema_for_response()

        response = client.responses.create(
            model=MODEL_NAME,
            # Enforce JSON schema output (Responses API)
            response_format={
                "type": "json_schema",
                "json_schema": schema,
            },
            # System + user prompts (Responses API prefers "input" content)
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_user_prompt(req),
                },
            ],
        )

        # Extract the JSON text from the first output
        content = response.output_text  # Convenient helper for Responses API
        if not content:
            raise HTTPException(status_code=502, detail="Empty response from model.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {e}")

        # Validate with Pydantic (gives us nice 422s if off)
        validated = AnalyzeResponse.model_validate(parsed)
        return validated

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Dev entry ----------
if __name__ == "__main__":
    # For local runs: uvicorn ai_analyzer_server:app --reload
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
