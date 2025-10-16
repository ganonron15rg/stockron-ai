import time
import requests
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from tradingview_ta import TA_Handler, Interval

# ===== הגדרות =====
SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"
CREDENTIALS_FILE = "credentials.json"
API_KEY_FMP = "PUhplkSpkYiXeUWJqlnrX1rWB26TrzaM"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# ===== חיבור לשיטס =====
def get_sheet(name="StockData"):
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    try:
        return client.open_by_key(SHEET_ID).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_key(SHEET_ID).add_worksheet(title=name, rows=1000, cols=20)
        return sheet

# ===== מקור נתונים מ-FMP =====
def get_from_fmp(symbol):
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={API_KEY_FMP}"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            d = data[0]
            return {
                "marketCap": d.get("mktCap"),
                "priceToBook": d.get("priceToBook"),
                "priceToSales": d.get("priceToSalesRatioTTM"),
                "pegRatio": d.get("pegRatio"),
                "trailingPE": d.get("pe")
            }
        else:
            return {}
    except Exception as e:
        print(f"❌ שגיאה ב-FMP ({symbol}): {e}")
        return {}

# ===== TradingView =====
def get_from_tradingview(symbol):
    """מביא אינדיקטורים טכניים מ-TradingView עם התאמה אוטומטית לבורסה"""
    try:
        # זיהוי בורסה לפי סימול
        exchange = "NASDAQ"
        if symbol in ["PLX", "POET"]:
            exchange = "AMEX"
        elif symbol in ["TSLA", "NVDA", "AAPL"]:
            exchange = "NASDAQ"

        handler = TA_Handler(
            symbol=symbol,
            screener="america",
            exchange=exchange,
            interval=Interval.INTERVAL_1_DAY
        )

        analysis = handler.get_analysis()
        indicators = analysis.indicators

        return {
            "rsi": round(indicators.get("RSI", 0), 2),
            "macd": round(indicators.get("MACD.macd", 0), 2),
            "recommendation": analysis.summary.get("RECOMMENDATION", "N/A")
        }

    except Exception as e:
        print(f"⚠️ שגיאה ב-TradingView עבור {symbol}: {e}")
        return {"rsi": None, "macd": None, "recommendation": "N/A"}

# ===== שילוב מקורות =====
def get_full_stock_data(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    data = {
        "symbol": symbol,
        "name": info.get("shortName", ""),
        "price": info.get("currentPrice", info.get("regularMarketPrice")),
        "open": info.get("open"),
        "previousClose": info.get("previousClose"),
        "dayHigh": info.get("dayHigh"),
        "dayLow": info.get("dayLow"),
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        "volume": info.get("volume"),
        "marketCap": info.get("marketCap"),
        "trailingPE": info.get("trailingPE"),
        "priceToBook": info.get("priceToBook"),
        "priceToSales": info.get("priceToSalesTrailing12Months"),
        "pegRatio": info.get("pegRatio"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }

    missing = [k for k, v in data.items() if not v]
    if missing:
        print(f"⚠️ חסרים נתונים ב-{symbol}: {missing}, משלים מ-FMP...")
        fmp_data = get_from_fmp(symbol)
        for k in missing:
            if k in fmp_data and fmp_data[k]:
                data[k] = fmp_data[k]

    # --- הוספת נתוני TradingView ---
    tv_data = get_from_tradingview(symbol)
    data.update(tv_data)

    return data

# ===== כתיבה לשיטס =====
def update_stockdata(symbols):
    sheet = get_sheet("StockData")

    header = [
        "Time", "Symbol", "Name", "Price", "Open", "Prev Close",
        "Day High", "Day Low", "52W High", "52W Low",
        "Volume", "Market Cap", "P/E", "P/B", "P/S", "PEG",
        "Sector", "Industry",
        "RSI", "MACD", "Recommendation"
    ]
    sheet.clear()
    sheet.append_row(header)

    rows = []
    for sym in symbols:
        stock = get_full_stock_data(sym)
        row = [
            time.strftime("%Y-%m-%d %H:%M:%S"),
            stock.get("symbol"),
            stock.get("name"),
            stock.get("price"),
            stock.get("open"),
            stock.get("previousClose"),
            stock.get("dayHigh"),
            stock.get("dayLow"),
            stock.get("fiftyTwoWeekHigh"),
            stock.get("fiftyTwoWeekLow"),
            stock.get("volume"),
            stock.get("marketCap"),
            stock.get("trailingPE"),
            stock.get("priceToBook"),
            stock.get("priceToSales"),
            stock.get("pegRatio"),
            stock.get("sector"),
            stock.get("industry"),
            stock.get("rsi"),
            stock.get("macd"),
            stock.get("recommendation")
        ]
        rows.append(row)
        print(f"✅ עודכנה מניה: {sym}")

    sheet.append_rows(rows)
    print(f"💾 נכתבו {len(rows)} שורות חדשות ל-StockData (מלאות)")

# ===== לולאת Poller =====
def poller_loop(interval_minutes=3):
    symbols = ["AAPL", "TSLA", "NVDA", "PLX", "POET"]
    print("\n🚀 Poller פועל – יעדכן כל", interval_minutes, "דקות.")
    print("🔎 רשימת מניות נוכחית:", symbols)

    while True:
        update_stockdata(symbols)
        print("🕒 סבב הסתיים (", time.strftime("%H:%M:%S"), ")")
        print(f"מחכה {interval_minutes} דקות...\n")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    poller_loop(interval_minutes=3)
