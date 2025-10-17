from fastapi import FastAPI
from pydantic import BaseModel
import openai
import os
import pandas as pd

# הגדרת האפליקציה של FastAPI
app = FastAPI()

# קריאה למפתח API (אתה מוסיף אותו ב-Render תחת Environment Variables בשם OPENAI_API_KEY)
openai.api_key = os.getenv("OPENAI_API_KEY")

# נקודת בדיקה בסיסית
@app.get("/")
def root():
    return {"status": "ok", "message": "AI Analyzer server is running 🎯"}

# מודל נתונים לבקשות ניתוח
class AnalyzeRequest(BaseModel):
    ticker: str

# API לניתוח מניה (לדוגמה AAPL)
@app.post("/analyze")
async def analyze_stock(req: AnalyzeRequest):
    try:
        ticker = req.ticker.upper()
        # קריאה לדוגמה - אפשר להרחיב בהמשך עם נתונים אמיתיים
        analysis_text = f"ניתוח פונדמנטלי בסיסי עבור {ticker}:\n\n"
        analysis_text += "- הכנסות: צמיחה מתונה בשנים האחרונות 📈\n"
        analysis_text += "- רווחיות: יציבה וגבוהה מהממוצע בענף 💰\n"
        analysis_text += "- הערכת שוק: שווי גבוה אך מוצדק יחסית לנתונים 📊\n"
        analysis_text += "- תחזית: צפי להמשך צמיחה בטווח בינוני 🧭\n"

        return {"ticker": ticker, "analysis": analysis_text}
    except Exception as e:
        return {"error": str(e)}
