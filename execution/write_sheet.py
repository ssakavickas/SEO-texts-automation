import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
SHEET_ID = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"
BLOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitter_competitor_tracking_blog.md')

def main():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    with open(BLOG_FILE, 'r') as f:
        content = f.read().strip()
        # Keep all newlines intact so that Markdown code blocks and lists
        # retain their vertical formatting in the spreadsheet cell.
    
    # Adding input mock data to Contentas (B2) and the generated markdown to Rezultatas (C2)
    sheet.update_acell('B2', 'Topic: Twitter Competitor Tracking\nPrimary Keyword: tracking competitors twitter')
    sheet.update_acell('C2', content)
    
    print("Successfully wrote the blog post to Google Sheets (C2).")

if __name__ == "__main__":
    main()
