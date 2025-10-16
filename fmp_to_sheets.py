import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ========= הגדרות =========
SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"  # ה-ID של הגיליון שלך
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# ========= פונקציה להבאת נתונים =========
def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        data = {
            "symbol": symbol.upper(),
            "name": info.get("shortName", ""),
            "price": info.get("currentPrice", ""),
            "changesPercentage": info.get("regularMarketChangePercent", ""),
            "marketCap": info.get("marketCap", ""),
            "trailingPE": info.get("trailingPE", ""),
            "pegRatio": info.get("pegRatio", "")
        }
        return data
    except Exception as e:
        print(f"❌ שגיאה בהבאת הנתונים: {e}")
        return None

# ========= כתיבה לגוגל שיטס =========
def write_to_sheets(data):
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1

    row = [
        data["symbol"],
        data["name"],
        data["price"],
        data["changesPercentage"],
        data["marketCap"],
        data["trailingPE"],
        data["pegRatio"]
    ]
    sheet.append_row(row)
    print(f"✅ נכתב לגיליון: {data['symbol']}")

# ========= הרצה =========
if __name__ == "__main__":
    symbol = input("הכנס טיקר (למשל AAPL, TSLA, MSFT): ").upper()
    stock = get_stock_data(symbol)
    if stock:
        write_to_sheets(stock)
    else:
        print("❌ לא נמצאו נתונים לטיקר הזה.")
