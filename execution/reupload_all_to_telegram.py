import os
import glob
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_keys() -> dict:
    keys = {}
    key_file = os.path.join(BASE_DIR, "anthropic_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys

keys = load_keys()
TELEGRAM_BOT_TOKEN = keys.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = keys.get("TELEGRAM_CHAT_ID")

def extract_topic_from_html(html_path):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        soup = BeautifulSoup(content, 'html.parser')
        h1 = soup.find('h1')
        if h1 and h1.text.strip().lower() != "blog post package":
            return h1.text.strip()
        elif h1 and h1.text.strip().lower() == "blog post package":
            headers = soup.find_all(['h1', 'h2'])
            ignore_list = ["blog post package", "seo metadata", "linkedin post", "twitter thread", "blog cover image"]
            for h in headers:
                if h.text.strip().lower() not in ignore_list:
                    return h.text.strip()
        # Fallback to logic pulling from filename
        return os.path.basename(html_path).replace("_CONSOLIDATED.html", "").replace("_blog", "").replace("_", " ").title()
    except Exception as e:
        print(f"Error extracting topic from {html_path}: {e}")
        return "New Blog Post"

def send_with_retry(method, url, data=None, files=None, max_retries=5, delay=5):
    """Robust retry logic with exponential backoff for Telegram API limits."""
    for attempt in range(max_retries):
        try:
            if method == 'post':
                # Re-open files for each attempt to avoid 'ValueError: I/O operation on closed file'
                fresh_files = {}
                if files:
                    for k, v in files.items():
                        if isinstance(v, tuple):
                            filename, filepath, content_type = v
                            fresh_files[k] = (filename, open(filepath, 'rb'), content_type)
                
                response = requests.post(url, data=data, files=fresh_files)
                
                # Close any opened files
                for k, v in fresh_files.items():
                    if hasattr(v[1], 'close'):
                        v[1].close()

            else:
                response = requests.get(url, params=data)
            
            if response.status_code == 429:
                retry_after = response.json().get('parameters', {}).get('retry_after', delay)
                print(f"  [429 Rate Limit] Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            wait_time = delay * (2 ** attempt)
            print(f"  [Error] {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            
    print(f"  [Failed] Could not complete request after {max_retries} attempts.")
    return None

def send_to_telegram(topic, html_path, cover_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not found.")
        return False
        
    print(f"Sending package for: {topic}")
    
    # Send Photo
    if os.path.exists(cover_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"✅ **{topic}** is ready and successfully generated!",
            "parse_mode": "Markdown"
        }
        files = {"photo": (os.path.basename(cover_path), cover_path, "image/png")}
        print("  -> Uploading Cover Image...")
        send_with_retry('post', url, data=data, files=files)
    else:
        print(f"  -> WARNING: No cover image found at {cover_path}")
        
    # Send HTML File
    if os.path.exists(html_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        data = {"chat_id": TELEGRAM_CHAT_ID}
        files = {"document": (os.path.basename(html_path), html_path, "text/html")}
        print("  -> Uploading HTML Document...")
        send_with_retry('post', url, data=data, files=files)
        
    return True

def main():
    html_files = glob.glob(os.path.join(BASE_DIR, "*_CONSOLIDATED.html"))
    print(f"Found {len(html_files)} consolidated blog packages to re-upload.\n")
    
    for html_path in sorted(html_files):
        topic = extract_topic_from_html(html_path)
        base = os.path.basename(html_path).replace("_CONSOLIDATED.html", "")
        # Find exact matches that exist
        cover_path = os.path.join(BASE_DIR, f"{base}_cover.png")
        if not os.path.exists(cover_path):
            cover_path = os.path.join(BASE_DIR, f"{base}_blog_cover.png")
            
        if not os.path.exists(cover_path):
            # Try fuzzy matching without "what's" smart quotes issue
            fuzzy_base = base.replace("whats", "what’s").replace("what_s", "what’s")
            fuzzy_path = os.path.join(BASE_DIR, f"{fuzzy_base}_cover.png")
            if os.path.exists(fuzzy_path):
                cover_path = fuzzy_path
            else:
                fuzzy_base_2 = base.replace("what’s", "whats").replace("what_s", "whats")
                fuzzy_path_2 = os.path.join(BASE_DIR, f"{fuzzy_base_2}_cover.png")
                if os.path.exists(fuzzy_path_2):
                    cover_path = fuzzy_path_2
                
        if not os.path.exists(cover_path):
            print(f"Skipping {base} - Needs cover image regeneration")
            continue
            
        send_to_telegram(topic, html_path, cover_path)
        print("  Waiting 5 seconds before next package...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()
