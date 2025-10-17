# ========== ai_analyzer_server.py ==========
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import yfinance as yf
import os

# === הגדרות OpenAI ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === אפליקציית FastAPI ===
app = FastAPI(title="Stockron AI Analyzer", version="2.0")

# === בדיקת חיבור בסיסית ===
@app.get("/")
def root():
    return {"status": "ok", "message": "AI Analyzer server is running 🎯"}

# === מודל הבקשה ===
class AnalyzeRequest(BaseModel):
    ticker: str

# === פונקציה שמביאה נתונים מ-Yahoo Finance ===
def get_stock_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "Symbol": ticker.upper(),
            "Name": info.get("shortName"),
            "Sector": info.get("sector"),
            "Market Cap": info.get("marketCap"),
            "P/E Ratio": info.get("trailingPE"),
            "Price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "EPS": info.get("trailingEps"),
            "PEG Ratio": info.get("pegRatio"),
            "Dividend Yield": info.get("dividendYield"),
            "Beta": info.get("beta"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data: {e}")

# === פונקציה לניתוח עם GPT ===
def analyze_with_gpt(data: dict):
    prompt = f"""
    נתח את המניה הבאה לפי הנתונים הפונדמנטליים:
    {data}

    כתוב ניתוח קצר בעברית:
    - תמחור (גבוה / סביר / נמוך)
    - קצב צמיחה
    - סיכון כללי
    - פוטנציאל לטווח קצר וארוך
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "אתה אנליסט שוק ההון מומחה."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

# === הנתיב הראשי לניתוח מניה ===
@app.post("/analyze")
def analyze_stock(request: AnalyzeRequest):
    data = get_stock_data(request.ticker)
    analysis = analyze_with_gpt(data)
    return {"data": data, "ai_analysis": analysis}

# === אופציונלי: ניתוח רשימת מניות ===
class AnalyzeListRequest(BaseModel):
    tickers: list[str]

@app.post("/analyze_list")
def analyze_multiple(request: AnalyzeListRequest):
    results = []
    for t in request.tickers:
        try:
            data = get_stock_data(t)
            analysis = analyze_with_gpt(data)
            results.append({"symbol": t, "data": data, "analysis": analysis})
        except Exception as e:
            results.append({"symbol": t, "error": str(e)})
    return {"results": results}

# ========== סוף הקובץ ==========
