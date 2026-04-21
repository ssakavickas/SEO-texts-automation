import os
import json
import subprocess
import time
import sys
import gspread
from google.oauth2.service_account import Credentials

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
SHEET_ID = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"
INPUT_FILE = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")
PIPELINE_PATH = os.path.join(BASE_DIR, "execution", "pipeline.py")

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_sheet():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def run_batch_from_sheet():
    sheet = get_sheet()
    all_values = sheet.get_all_values()
    if not all_values:
        return
    headers = all_values[0]
    records = []
    for row in all_values[1:]:
        padded = row + [''] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded)))
    
    # Dynamic header detection
    def find_idx(name_list):
        for name in name_list:
            for i, h in enumerate(headers):
                if name.lower() in h.lower():
                    return i + 1
        return None

    topic_col = find_idx(["topic", "tema"])
    kw_col = find_idx(["primary keyword", "raktažodis"])
    wc_col = find_idx(["word count", "žodžių skaičius"])
    status_col = find_idx(["status", "process", "būsena"])

    if not status_col:
        # Fallback to column 4 or 5 if not found
        status_col = len(headers) if len(headers) >= 4 else 4

    # Identify which rows to process
    pending_rows = []
    for i, row in enumerate(records):
        # We find status by column name or last column
        status_val = ""
        header_keys = list(row.keys())
        for key in header_keys:
            if "status" in key.lower() or "process" in key.lower():
                status_val = str(row[key]).strip().lower()
                break
        
        if status_val in ['', 'pending', 'todo']:
            pending_rows.append((i + 2, row)) 
            
    if not pending_rows:
        print("✅ No pending rows found in Google Sheets.")
        return

    print(f"🚀 Found {len(pending_rows)} pending articles. Starting batch processing...")

    for row_idx, row_data in pending_rows:
        # Extract data using varied key possibilities
        def get_val(names, default=""):
            for k in row_data.keys():
                for n in names:
                    if n.lower() in k.lower():
                        return row_data[k]
            return default

        topic = get_val(["topic", "tema"])
        if not topic:
            continue
            
        print(f"\nProcessing row {row_idx}: {topic}")
        
        # Prepare inputs
        data = {
            "topic": topic,
            "primary_keyword": get_val(["primary keyword", "raktažodis"], topic),
            "secondary_keywords": "", 
            "word_count": int(get_val(["word count"], 1500)) if str(get_val(["word count"])).isdigit() else 1500,
            "row_idx": row_idx
        }
        
        os.makedirs(os.path.dirname(INPUT_FILE), exist_ok=True)
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        # Update status to Processing
        sheet.update_cell(row_idx, status_col, "🔄 Processing...")
        
        try:
            subprocess.run([sys.executable, "-u", PIPELINE_PATH], check=True)
            
            # Update status to Completed
            sheet.update_cell(row_idx, status_col, "✅ Completed")
            print(f"✅ Finished row {row_idx}")
            
        except Exception as e:
            print(f"❌ Error in row {row_idx}: {e}")
            sheet.update_cell(row_idx, status_col, f"❌ Error: {str(e)[:50]}")
            
        time.sleep(2)

    print("\n🎉 Batch processing complete!")

if __name__ == "__main__":
    run_batch_from_sheet()
