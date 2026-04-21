import os
import re
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
SHEET_ID = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"
BLOG_FILE = os.path.join(BASE_DIR, 'twitter_competitor_tracking_blog.md')

def apply_rich_text(sheet, cell, markdown_text):
    """
    Parses simple markdown (Code blocks, Headers, Bold) and converts it to
    Google Sheets Rich Text Format updates.
    """
    # 1. We strip formatting marks for clean text but keep indices for styling
    clean_text = ""
    formats = []
    
    lines = markdown_text.split('\n')
    in_code_block = False
    
    current_index = 0
    
    for line in lines:
        if line.startswith('```'):
            in_code_block = not in_code_block
            continue
            
        start_idx = current_index
        
        if in_code_block:
            clean_text += line + "\n"
            current_index += len(line) + 1
            formats.append({
                "startIndex": start_idx,
                "endIndex": current_index,
                "textFormat": {
                    "fontFamily": "Courier New",
                    "foregroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}
                }
            })
            continue

        # Check for headers
        is_header = False
        if re.match(r'^#{1,6}\s+', line):
            line = re.sub(r'^#{1,6}\s+', '', line)
            is_header = True
        elif re.match(r'^[A-Z\s]+$', line) and len(line) > 5 and not "SEO PACK" in line:
            is_header = True

        # Process inline bold (**text**)
        clean_line = ""
        line_formats = []
        i = 0
        in_bold = False
        bold_start = -1
        
        while i < len(line):
            if line[i:i+2] == '**':
                if not in_bold:
                    in_bold = True
                    bold_start = current_index + len(clean_line)
                else:
                    in_bold = False
                    line_formats.append({
                        "startIndex": bold_start,
                        "endIndex": current_index + len(clean_line),
                        "textFormat": {"bold": True}
                    })
                i += 2
            else:
                clean_line += line[i]
                i += 1

        clean_text += clean_line + "\n"
        
        # Apply header format if applicable
        if is_header:
            formats.append({
                "startIndex": start_idx,
                "endIndex": current_index + len(clean_line),
                "textFormat": {
                    "bold": True,
                    "fontSize": 12
                }
            })
            
        formats.extend(line_formats)
        current_index += len(clean_line) + 1
            
    # Send basic text value first
    sheet.update_acell(cell, clean_text)
    
    # Then apply rich text formatting
    # GSpread doesn't natively support rich text cells well, so we have to use batch_update via the API
    worksheet_id = sheet.id
    row, col = gspread.utils.a1_to_rowcol(cell)
    
    # Needs to be 0-indexed for the API
    row_idx = row - 1
    col_idx = col - 1
    
    requests = [
        {
            "updateCells": {
                "range": {
                    "sheetId": worksheet_id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": clean_text},
                                "textFormatRuns": [
                                    {"startIndex": f["startIndex"], "format": f["textFormat"]}
                                    for f in formats
                                ]
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue,textFormatRuns"
            }
        }
    ]
    
    try:
        sheet.spreadsheet.batch_update({"requests": requests})
        print("Rich text formatting applied successfully.")
    except Exception as e:
        print(f"Failed to apply rich text: {e}")


def main():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    with open(BLOG_FILE, 'r') as f:
        content = f.read().strip()
    
    sheet.update_acell('B2', 'Topic: Twitter Competitor Tracking\nPrimary Keyword: tracking competitors twitter')
    
    print("Uploading formatted text to C2...")
    apply_rich_text(sheet, 'C2', content)

if __name__ == "__main__":
    main()
