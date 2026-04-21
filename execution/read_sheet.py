import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Scopes required for Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
OUTPUT_FILE = os.path.join(TMP_DIR, 'blog_inputs.json')

SHEET_ID = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"

def get_sheet_data():
    if not os.path.exists(CREDENTIALS_FILE):
        print("Error: credentials.json not found.")
        return
    
    # Authenticate
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    try:
        # Open the spreadsheet
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        # Get all records (list of dicts)
        records = sheet.get_all_records()
        
        # Ensure .tmp exists
        os.makedirs(TMP_DIR, exist_ok=True)
        
        # Save records
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(records, f, indent=2)
            
        print(f"Successfully read {len(records)} rows from Google Sheets.")
        print(f"Saved to {OUTPUT_FILE}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error accessing Google Sheets: {e}")

if __name__ == "__main__":
    get_sheet_data()
