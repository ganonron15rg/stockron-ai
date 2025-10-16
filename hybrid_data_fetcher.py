import requests
import yfinance as yf

API_KEY_FMP = "PUhplkSpkYiXeUWJqlnrX1rWB26TrzaM"  # מפתח שלך מ-FMP


def get_from_fmp(symbol):
    """מביא נתונים חסרים מ-FMP"""
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={API_KEY_FMP}"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            d = data[0]
            return {
                "symbol": symbol,
                "marketCap": d.get("mktCap"),
                "priceToBook": d.get("priceToBook"),
                "priceToSales": d.get("priceToSalesRatioTTM"),
                "pegRatio": d.get("pegRatio"),
                "trailingPE": d.get("pe"),
            }
        else:
            return {}
    except Exception as e:
        print(f"❌ שגיאה ב-FMP ({symbol}): {e}")
        return {}


def get_full_stock_data(symbol):
    """משלב בין Yahoo Finance ל-FMP למידע מלא"""
    ticker = yf.Ticker(symbol)
    info = ticker.info

    data = {
        "symbol": symbol,
        "name": info.get("shortName", ""),
        "price": info.get("currentPrice", info.get("regularMarketPrice")),
        "marketCap": info.get("marketCap"),
        "trailingPE": info.get("trailingPE"),
        "priceToBook": info.get("priceToBook"),
        "priceToSales": info.get("priceToSalesTrailing12Months"),
        "pegRatio": info.get("pegRatio"),
    }

    # בדוק אילו שדות חסרים
    missing = [k for k, v in data.items() if not v or v == "N/A"]
    if missing:
        print(f"⚠️ חסרים נתונים ב-{symbol}: {missing}, משלים מ-FMP...")
        fmp_data = get_from_fmp(symbol)
        for k in missing:
            if k in fmp_data and fmp_data[k]:
                data[k] = fmp_data[k]

    return data


if __name__ == "__main__":
    symbols = ["AAPL", "TSLA", "NVDA", "PLX", "POET"]
    for s in symbols:
        full = get_full_stock_data(s)
        print(f"\n✅ נתונים מלאים ל-{s}:")
        for k, v in full.items():
            print(f"{k}: {v}")
