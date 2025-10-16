from fastapi import FastAPI
import openai
import os
import pandas as pd
app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "message": "AI Analyzer server is running"}
# ===================== הגדרות =====================
SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

openai.api_key = os.getenv("OPENAI_API_KEY")  # שים משתנה סביבה עם מפתח ה-GPT שלך

app = FastAPI(title="AI Analyzer Server")

class AnalyzeRequest(BaseModel):
    symbol: str
    fundamentals: dict

# ===================== חיבור לשיטס =====================
def get_sheet(name):
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(SHEET_ID)
    try:
        return ss.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=500, cols=20)

# ===================== ניתוח GPT =====================
def run_ai_analysis(symbol, fundamentals):
    prompt = f"""
    אתה אנליסט פיננסי בכיר. נתח את מניית {symbol} לפי הנתונים הבאים:

    נתונים כמותיים:
    {fundamentals}

    בצע ניתוח לפי השאלות הבאות:
    1. האם ההכנסות והרווחים צפויים לצמוח?
    2. האם קצב הצמיחה גבוה מהממוצע בסקטור?
    3. מהם מנועי הצמיחה העיקריים?
    4. מהם הסיכונים המרכזיים לחברה?
    5. כיצד הערכת השווי שלה ביחס למתחרות?
    6. מה התחזית הכוללת (חיובית / ניטרלית / שלילית)?

    החזר ניתוח תמציתי (5–8 משפטים) בעברית, עם סיכום איכותי ומסקנה ברורה.
    """

    response = openai.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )
    return response.choices[0].message.content.strip()

# ===================== API Endpoint =====================
@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    print(f"🔎 מריץ ניתוח עבור {request.symbol}...")
    insights = get_sheet("AI_Insights")

    result = run_ai_analysis(request.symbol, request.fundamentals)
    insights.append_row([request.symbol, result])

    print(f"✅ ניתוח הושלם עבור {request.symbol}")
    return {"symbol": request.symbol, "analysis": result}
