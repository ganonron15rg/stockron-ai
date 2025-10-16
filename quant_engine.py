import math
import statistics as stats
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ========= הגדרות =========
SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# ========= כלי עזר =========
def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

def get_ws(name):
    client = get_client()
    ss = client.open_by_key(SHEET_ID)
    try:
        return ss.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=2000, cols=50)

def to_float(x):
    try:
        if x in ("", None, "N/A"): return None
        return float(x)
    except Exception:
        return None

def safe_pct_change(now_val, prev_val):
    now_val, prev_val = to_float(now_val), to_float(prev_val)
    if now_val is None or prev_val is None or prev_val == 0: return None
    return (now_val - prev_val) / prev_val * 100.0

def zscore(val, series):
    try:
        xs = [to_float(v) for v in series if to_float(v) is not None]
        if not xs or val is None or len(xs) < 3: return None
        mu, sd = stats.mean(xs), stats.pstdev(xs)
        if sd == 0: return 0.0
        return (val - mu) / sd
    except Exception:
        return None

def star_scale(value, good_low=True, cutoffs=(1, 2, 3)):
    """
    מחזיר 0–3 כוכבים לפי ערך ומדלגים אם None.
    good_low=True -> נמוך זה טוב (למשל PE/PEG); אחרת גבוה זה טוב (למשל צמיחה).
    cutoffs = ספי דירוג פשוטים (Z או ערך ישיר).
    """
    if value is None: return 0
    v = value
    # אם הגענו עם Z-score, cutoff ~ 1,2,3; אם ערך רגיל – תשתמש במרווחים סבירים
    if good_low:
        if v <= cutoffs[0]: return 3
        if v <= cutoffs[1]: return 2
        if v <= cutoffs[2]: return 1
        return 0
    else:
        if v >= cutoffs[2]: return 3
        if v >= cutoffs[1]: return 2
        if v >= cutoffs[0]: return 1
        return 0

# ========= חישוב עיקרי =========
def run_quant():
    src = get_ws("StockData")
    dst = get_ws("QuantAnalysis")

    # קריאת כל הנתונים מהטבלה החיה
    rows = src.get_all_values()
    if not rows or len(rows) < 2:
        print("⚠️ אין נתונים ב-StockData")
        return

    header = rows[0]
    data = rows[1:]

    # מיפוי אינדקסים לפי כותרות
    idx = {name: i for i, name in enumerate(header)}

    # עמודות חובה בקלט
    req_cols = ["Symbol","Name","Sector","Industry","Price","Prev Close","P/E","P/B","P/S","PEG","RSI","Recommendation"]
    missing_cols = [c for c in req_cols if c not in idx]
    if missing_cols:
        print("⚠️ חסרות עמודות ב-StockData:", missing_cols)
        return

    # נבנה אוספים לחישובי ממוצעי סקטור (ל־Z-score)
    sector_buckets = {}
    for r in data:
        sector = r[idx["Sector"]] or "UNKNOWN"
        sector_buckets.setdefault(sector, {"pe": [], "ps": [], "pb": [], "peg": [], "price": []})
        sector_buckets[sector]["pe"].append(r[idx["P/E"]])
        sector_buckets[sector]["ps"].append(r[idx["P/S"]])
        sector_buckets[sector]["pb"].append(r[idx["P/B"]])
        sector_buckets[sector]["peg"].append(r[idx["PEG"]])
        sector_buckets[sector]["price"].append(r[idx["Price"]])

    # כתובת כותרות ל-QuantAnalysis
    out_header = [
        "Time","Symbol","Name","Sector","Industry",
        "Price","% Daily Change","PE","PS","PB","PEG","RSI","TechReco",
        "PE_z_inSector","PS_z_inSector","PB_z_inSector","PEG_flag",
        "Score_Value (PE/PEG)","Score_Growth (Δ%)","Score_Tech (RSI/Reco)",
        "Total_Score (0-9)","Notes"
    ]
    dst.clear()
    dst.append_row(out_header)

    out_rows = []
    for r in data:
        symbol   = r[idx["Symbol"]]
        name     = r[idx["Name"]]
        sector   = r[idx["Sector"]] or "UNKNOWN"
        industry = r[idx["Industry"]] or ""
        price    = to_float(r[idx["Price"]])
        prevc    = to_float(r[idx["Prev Close"]])
        pe       = to_float(r[idx["P/E"]])
        ps       = to_float(r[idx["P/S"]])
        pb       = to_float(r[idx["P/B"]])
        peg      = to_float(r[idx["PEG"]])
        rsi      = to_float(r[idx["RSI"]])  # יכול להיות None
        reco     = r[idx["Recommendation"]] if r[idx["Recommendation"]] else "N/A"

        # 1) שינוי יומי
        pct_day = safe_pct_change(price, prevc)

        # 2) Z-score בסקטור עבור מכפילים (נמוך עדיף)
        pe_z  = zscore(pe,  sector_buckets[sector]["pe"])
        ps_z  = zscore(ps,  sector_buckets[sector]["ps"])
        pb_z  = zscore(pb,  sector_buckets[sector]["pb"])

        # 3) דגל PEG: <1 נחשב טוב, 1–2 בינוני, >2 חלש, None = לא ידוע
        if peg is None:
            peg_flag = "N/A"
        elif peg < 1:
            peg_flag = "Good(<1)"
        elif peg <= 2:
            peg_flag = "Mid(1-2)"
        else:
            peg_flag = "High(>2)"

        # 4) ניקוד: Value (PE/PEG), Growth (שינוי יומי כללי כ-proxy), Tech (RSI+המלצה)
        # Value: משתמשים ב-Z ל-PE (נמוך=טוב) וב-PEG ישיר (נמוך=טוב)
        value_stars_pe  = star_scale(abs(pe_z) if pe_z is not None else None, good_low=True,  cutoffs=(0.5,1.0,1.5))
        value_stars_peg = star_scale(peg if peg is not None else None,      good_low=True,  cutoffs=(1.0,1.5,2.0))
        score_value = min(3, (value_stars_pe + value_stars_peg))  # 0–3

        # Growth: שינוי יומי – גבוה יותר עדיף (פשוט ל-MVP)
        growth_stars = star_scale(pct_day if pct_day is not None else None, good_low=False, cutoffs=(0.5,1.0,2.0))  # % שינוי
        score_growth = growth_stars  # 0–3

        # Tech: RSI באזור 50=ניטרלי; רחוק מ-50 פחות טוב. Reco של TV מוסיף נקודה אם BUY/STRONG_BUY
        tech_rsi_stars = None
        if rsi is None:
            tech_rsi_stars = 1  # ניטרלי אם חסר
        else:
            # קרוב ל-50 טוב: סטייה קטנה = יותר כוכבים
            dev = abs(rsi - 50)
            # 0–10 -> 3*, 10–20 -> 2*, 20–30 -> 1*, >30 -> 0
            if dev <= 10: tech_rsi_stars = 3
            elif dev <= 20: tech_rsi_stars = 2
            elif dev <= 30: tech_rsi_stars = 1
            else: tech_rsi_stars = 0

        reco_bonus = 0
        if isinstance(reco, str):
            reco_u = reco.upper()
            if "STRONG_BUY" in reco_u or reco_u == "BUY":
                reco_bonus = 1
            elif reco_u == "SELL" or "STRONG_SELL" in reco_u:
                reco_bonus = 0
        score_tech = min(3, tech_rsi_stars + reco_bonus)  # 0–3

        total = (score_value or 0) + (score_growth or 0) + (score_tech or 0)  # 0–9

        notes = []
        if pe is None: notes.append("PE missing")
        if peg is None: notes.append("PEG missing/NA")
        if rsi is None: notes.append("RSI NA")
        note_str = "; ".join(notes) if notes else ""

        out_rows.append([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol, name, sector, industry,
            price, None if pct_day is None else round(pct_day, 2),
            pe, ps, pb, peg, rsi, reco,
            None if pe_z is None else round(pe_z, 2),
            None if ps_z is None else round(ps_z, 2),
            None if pb_z is None else round(pb_z, 2),
            peg_flag,
            score_value, score_growth, score_tech,
            total, note_str
        ])

    # כתיבה מרוכזת
    if out_rows:
        dst.append_rows(out_rows, value_input_option="RAW")
        print(f"✅ QuantAnalysis נבנה: {len(out_rows)} שורות")
    else:
        print("⚠️ לא נמצאו שורות לניתוח")

if __name__ == "__main__":
    run_quant()
