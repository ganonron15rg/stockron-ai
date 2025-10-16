import yfinance as yf
import gspread
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from datetime import datetime

SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# ---------------- Google Sheets ----------------
def get_sheet(name):
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(SHEET_ID)
    try:
        return ss.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=2000, cols=50)

# ---------------- TradingView ----------------
def get_tradingview_data(symbol):
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "symbols": {"tickers": [f"NASDAQ:{symbol}"], "query": {"types": []}},
            "columns": ["price_earnings_ttm", "earnings_per_share_next_fy", "earnings_per_share_yoy_g"]
        }
        r = requests.post(url, json=payload)
        j = r.json()
        if j.get("data"):
            d = j["data"][0]["d"]
            return {
                "pe": d[0],
                "epsGrowth": d[2] if len(d) > 2 else d[1]
            }
    except Exception as e:
        print(f"⚠️ TradingView error for {symbol}: {e}")
    return {}

# ---------------- Google Finance Scraping ----------------
def get_googlefinance_data(symbol):
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:NASDAQ"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        # חיפוש PEG או EPS growth
        eps_growth = None
        if "EPS growth" in text:
            idx = text.find("EPS growth")
            snippet = text[idx:idx+50]
            num = ''.join(ch for ch in snippet if ch.isdigit() or ch == '.' or ch == '-')
            if num:
                eps_growth = float(num)

        pe_ratio = None
        if "P/E ratio" in text:
            idx = text.find("P/E ratio")
            snippet = text[idx:idx+40]
            num = ''.join(ch for ch in snippet if ch.isdigit() or ch == '.' or ch == '-')
            if num:
                pe_ratio = float(num)

        return {"pe": pe_ratio, "epsGrowth": eps_growth}
    except Exception:
        return {}

# ---------------- EPS Growth Calculation ----------------
def calculate_eps_growth(ticker):
    try:
        hist = ticker.get_earnings_dates(limit=4)
        if len(hist) >= 2:
            last_eps = hist["epsactual"].iloc[-1]
            prev_eps = hist["epsactual"].iloc[-2]
            if prev_eps and prev_eps != 0:
                growth = ((last_eps - prev_eps) / abs(prev_eps)) * 100
                return round(growth, 2)
    except Exception:
        pass
    return None

# ---------------- Combine All Sources ----------------
def get_full_fundamentals(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    data = {
        "symbol": symbol,
        "name": info.get("shortName", ""),
        "price": info.get("currentPrice", info.get("regularMarketPrice")),
        "trailingPE": info.get("trailingPE"),
        "epsGrowth": calculate_eps_growth(ticker)
    }

    # TradingView
    if not data["trailingPE"] or not data["epsGrowth"]:
        tv = get_tradingview_data(symbol)
        if not data["trailingPE"] and tv.get("pe"):
            data["trailingPE"] = tv["pe"]
        if not data["epsGrowth"] and tv.get("epsGrowth"):
            data["epsGrowth"] = tv["epsGrowth"]

    # Google Finance
    if not data["trailingPE"] or not data["epsGrowth"]:
        gf = get_googlefinance_data(symbol)
        if not data["trailingPE"] and gf.get("pe"):
            data["trailingPE"] = gf["pe"]
        if not data["epsGrowth"] and gf.get("epsGrowth"):
            data["epsGrowth"] = gf["epsGrowth"]

    return data

# ---------------- Write to Sheet ----------------
def enrich_to_sheets():
    src = get_sheet("StockData")
    dst = get_sheet("Fundamentals")

    rows = src.get_all_values()
    if len(rows) < 2:
        print("⚠️ אין נתונים ב-StockData")
        return

    header = rows[0]
    data = rows[1:]
    idx = {name: i for i, name in enumerate(header)}

    dst.clear()
    dst.append_row(["Time", "Symbol", "Name", "Price", "P/E", "EPS Growth (%)", "PEG (Formula)"])

    out_rows = []
    for r in data:
        symbol = r[idx.get("Symbol")]
        if not symbol:
            continue
        print(f"🔎 מעבד {symbol}...")
        fdata = get_full_fundamentals(symbol)
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            fdata["symbol"], fdata["name"], fdata["price"],
            fdata["trailingPE"], fdata["epsGrowth"], ""
        ]
        out_rows.append(row)

    if out_rows:
        dst.append_rows(out_rows)
        print(f"✅ נכתבו {len(out_rows)} שורות מלאות ל-Fundamentals")
        for i in range(2, len(out_rows) + 2):
            dst.update_acell(f"G{i}", f"=IFERROR(E{i}/F{i},\"\")")

if __name__ == "__main__":
    enrich_to_sheets()
