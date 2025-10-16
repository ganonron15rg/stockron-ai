import yfinance as yf

symbols = ["AAPL", "TSLA", "NVDA", "PLX", "POET"]
for symbol in symbols:
    ticker = yf.Ticker(symbol)
    info = ticker.info

    print(f"\n🔍 {symbol} - Available keys:")
    print(list(info.keys())[:40])  # מציג 40 השדות הראשונים
