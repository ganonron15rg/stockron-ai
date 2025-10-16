import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheet(name):
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(name)

def safe_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

def analyze_fundamentals():
    fundamentals = get_sheet("Fundamentals")
    ss = fundamentals.spreadsheet

    try:
        analysis = ss.worksheet("Analysis")
    except gspread.exceptions.WorksheetNotFound:
        analysis = ss.add_worksheet(title="Analysis", rows=200, cols=20)

    data = fundamentals.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        print("⚠️ אין נתונים לניתוח.")
        return

    df["P/E"] = df["P/E"].apply(safe_float)
    df["EPS Growth (%)"] = df["EPS Growth (%)"].apply(safe_float)

    df["PEG (calc)"] = df.apply(
        lambda x: round(x["P/E"] / x["EPS Growth (%)"], 2)
        if x["P/E"] and x["EPS Growth (%)"] not in [None, 0] else None,
        axis=1
    )

    def growth_rating(x):
        if x is None:
            return "N/A"
        elif x > 15:
            return "High"
        elif x > 5:
            return "Medium"
        else:
            return "Low"

    df["Growth Rating"] = df["EPS Growth (%)"].apply(growth_rating)

    def pe_rating(x):
        if x is None:
            return "N/A"
        elif x > 30:
            return "Overvalued"
        elif x > 10:
            return "Fair"
        else:
            return "Undervalued"

    df["PE Rating"] = df["P/E"].apply(pe_rating)

    def summary(x):
        return f"{x['Symbol']} – {x['Growth Rating']} growth, {x['PE Rating']} valuation, PEG={x['PEG (calc)'] if x['PEG (calc)'] else 'N/A'}."

    df["AI Summary"] = df.apply(summary, axis=1)

    # 👇 זה הפתרון – מחליף כל NaN במחרוזת ריקה
    df = df.fillna("")

    analysis.clear()
    analysis.append_row(list(df.columns))
    analysis.append_rows(df.values.tolist())
    print("✅ ניתוח פונדמנטלי בסיסי הושלם ונשמר בגיליון 'Analysis'.")

if __name__ == "__main__":
    analyze_fundamentals()
