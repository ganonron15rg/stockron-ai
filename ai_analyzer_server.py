from fastapi import FastAPI
from pydantic import BaseModel
import openai
import os
import yfinance as yf
import pandas as pd

app = FastAPI()

# הגדרת מפתח OpenAI (מוגדר ב-Render כ-Environment Variable)
openai.api_key = os.getenv("OPENAI_API_KEY")


# שורש לבדיקה
@app.get("/")
def root():
    return {"status": "ok", "message": "AI Analyzer server is running 🎯"}


# מודל בקשה
class AnalyzeRequest(BaseModel):
    ticker: str


# פונקציית ניתוח מניה
@app.post("/analyze")
async def analyze_stock(req: AnalyzeRequest):
    symbol = req.ticker.upper()
    try:
        # שליפת נתוני המניה
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # חילוץ נתונים מרכזיים
        data = {
            "Symbol": symbol,
            "Name": info.get("shortName", ""),
            "Price": info.get("currentPrice", ""),
            "Market Cap": info.get("marketCap", ""),
            "P/E Ratio": info.get("trailingPE", ""),
            "EPS (TTM)": info.get("trailingEps", ""),
            "Dividend Yield": info.get("dividendYield", ""),
            "PEG Ratio": info.get("pegRatio", ""),
            "Sector": info.get("sector", ""),
        }

        # יצירת פרומפט ל-GPT
        prompt = f"""
        בצע ניתוח פונדמנטלי תמציתי עבור מניית {data['Name']} ({symbol}):
        נתונים:
        מחיר נוכחי: {data['Price']}
        מכפיל רווח (P/E): {data['P/E Ratio']}
        תשואת דיבידנד: {data['Dividend Yield']}
        PEG Ratio: {data['PEG Ratio']}
        מגזר: {data['Sector']}

        נתח את הכדאיות להשקעה, סיכון מול סיכוי, והאם המניה נראית אטרקטיבית בטווח בינוני.
        """

        # קריאה ל-OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        analysis_text = response.choices[0].message["content"].strip()

        return {"data": data, "ai_analysis": analysis_text}

    except Exception as e:
        return {"error": str(e)}
