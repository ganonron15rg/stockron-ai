import gspread
from google.oauth2.service_account import Credentials

CREDENTIALS_FILE = "credentials.json"  # שם הקובץ שהורדת מגוגל
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SHEET_ID = "1YTrPFfnpjaJN6r779kYrGxfVSa2zNXCH_RrfLYmSHMM"

def test_google_sheets():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    sheet.append_row(["AAPL", "Test", "123", "It works!"])
    print("✅ נכתב בהצלחה לגוגל שיטס!")

if __name__ == "__main__":
    test_google_sheets()
