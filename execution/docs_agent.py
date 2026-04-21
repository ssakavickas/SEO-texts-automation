"""
docs_agent.py

Reads the current blog topic from Google Sheets (or fallback).
Queries Claude to decide which ScrapeBadger documentation pages are relevant to the topic.
Fetches the content of those specific documentation pages.
Saves the aggregated documentation as context to .tmp/docs_context.txt for the Blog Writer.

Usage:
    python3 execution/docs_agent.py
"""

import os
import json
import re
import requests
import anthropic
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_FILE   = os.path.join(BASE_DIR, "anthropic_key.txt")
OUTPUT_DIR  = os.path.join(BASE_DIR, ".tmp")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "docs_context.txt")
CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")

# ── Google Sheets ─────────────────────────────────────────────────────────────
SHEET_ID = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"
SCOPES   = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Blog Inputs (loaded dynamically) ──────────────────────────────────────────
TOPIC              = ""
PRIMARY_KEYWORD    = ""
SECONDARY_KEYWORDS = ""

# ── Available Docs Pages ──────────────────────────────────────────────────────
# Map of page title/description to URL
DOCS_PAGES = {}

def load_docs_pages_from_sitemap():
    global DOCS_PAGES
    try:
        resp = requests.get("https://docs.scrapebadger.com/sitemap.xml", timeout=10)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        
        # Strip xmlns if present for easier parsing
        xml_text = re.sub(r'\sxmlns="[^"]+"', '', resp.text, count=1)
        root = ET.fromstring(xml_text)
        
        for loc in root.findall('.//loc'):
            if not loc.text: continue
            url = loc.text.strip()
            path = url.replace("https://docs.scrapebadger.com", "").strip("/")
            if not path:
                title = "Home"
            else:
                title = path.replace("/", " - ").replace("-", " ").title()
                
            # Filter somewhat to not include pure xml stuff, though sitemap is all good URLs.
            DOCS_PAGES[title] = url
            
        print(f"  🌐 Loaded {len(DOCS_PAGES)} documentation pages dynamically from sitemap.")
    except Exception as e:
        print(f"  ⚠️ Failed to load sitemap ({e}). Falling back to static list.")
        DOCS_PAGES.update({
            "Quick Start": "https://docs.scrapebadger.com/quickstart",
            "Authentication": "https://docs.scrapebadger.com/authentication",
            "Twitter API - Tweets": "https://docs.scrapebadger.com/twitter/tweets",
            "Twitter Streams - Webhooks": "https://docs.scrapebadger.com/twitter-streams/webhooks",
            "Web Scraping - Overview": "https://docs.scrapebadger.com/web-scraping/overview"
        })


def load_keys() -> dict:
    keys = {}
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys


def load_inputs_from_sheet():
    global TOPIC, PRIMARY_KEYWORD, SECONDARY_KEYWORDS

    # 1. Check for Telegram Override FIRST
    override_file = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")
    if os.path.exists(override_file):
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
                TOPIC              = data.get("topic", "How to Track Competitors on Twitter")
                PRIMARY_KEYWORD    = data.get("primary_keyword", "")
                SECONDARY_KEYWORDS = data.get("secondary_keywords", "")
                print(f"  📋 Docs Agent Topic (from Telegram Override): {TOPIC}")
                return # Exit early, don't read from Sheets
        except Exception as e:
            print(f"  ⚠️ Could not read Telegram override ({e})")

    # 2. Fallback to Google Sheets
    try:
        creds  = Credentials.from_service_account_file(CREDENTIALS, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(SHEET_ID).sheet1
        row    = sheet.row_values(2)

        TOPIC              = row[0].strip() if len(row) > 0 else "How to Track Competitors on Twitter"
        PRIMARY_KEYWORD    = row[1].strip() if len(row) > 1 else ""
        SECONDARY_KEYWORDS = row[2].strip() if len(row) > 2 else ""
        print(f"  📋 Docs Agent Topic: {TOPIC}")
    except Exception as e:
        print(f"  ⚠️ Could not read from Sheet ({e}) — using fallback topic.")
        TOPIC = "How to Track Competitors on Twitter"


def select_relevant_pages(api_key: str) -> list[str]:
    """Ask Claude which doc pages are relevant to the current topic."""
    client = anthropic.Anthropic(api_key=api_key)
    
    pages_list = "\n".join([f"- {title}" for title in DOCS_PAGES.keys()])
    
    prompt = f"""
I am writing a blog post about: "{TOPIC}"
Keywords: {PRIMARY_KEYWORD}, {SECONDARY_KEYWORDS}

Here is the list of available API documentation pages for our tool, ScrapeBadger:
{pages_list}

Which 1 to 3 documentation pages are the MOST relevant for this blog post topic? 
For example, if the topic is about tracking competitors, "Twitter API - Users" and "Twitter API - Tweets" might be relevant to fetch their follower lists and recent tweets.
If the topic is about realtime alerting, "Twitter Streams - Filter Rules" and "Twitter Streams - Webhooks" are relevant.

CRITICAL RULE: If the topic is very general or completely unrelated to these specific API endpoints, do NOT force a match. It is perfectly fine to return an empty array. ONLY select pages that are genuinely, directly useful for the topic.

Return ONLY a JSON array of the exact titles from the list above. No other text. 
Example if relevant: ["Twitter API - Tweets", "Authentication (API Keys)"]
Example if NOT relevant: []
"""

    print("🧠 Asking Claude to select relevant doc pages...")
    
    # Read model from config, fallback to current latest alias
    keys = load_keys()
    model_name = keys.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    
    message = client.messages.create(
        model=model_name,
        max_tokens=1000,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    
    print(f"  [DEBUG] Claude Raw Response: {response_text}")
    try:
        # Step 1: try direct JSON loads
        try:
            selected_titles = json.loads(response_text)
        except json.JSONDecodeError:
            # Step 2: Extract just the JSON array part
            match = re.search(r'\[(.*?)\]', response_text, re.DOTALL)
            if match:
                selected_titles = json.loads(f"[{match.group(1)}]")
            else:
                selected_titles = []
                
        if not isinstance(selected_titles, list):
            selected_titles = []
        
        # Filter to only exact matches
        # Filter by checking if Claude's title is a substring of the actual DOCS_PAGES key
        valid_titles = []
        for exact_key in DOCS_PAGES.keys():
            if any(t.lower() in exact_key.lower() for t in selected_titles):
                valid_titles.append(exact_key)
                
        return valid_titles
    except Exception as e:
        print(f"  ⚠️ Error parsing Claude's page selection: {e}")
        # Fallback: try to match titles directly in string
        valid_titles = [t for t in DOCS_PAGES if t in response_text]
        return valid_titles


def fetch_page_text(url: str) -> str:
    """Fetch URL and extract the main text using BeautifulSoup."""
    try:
        headers = {"User-Agent": "ScrapeBadger-Docs-Agent/1.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Try to find main content areas (Nextra/Tailwind docs often use `main` or specific article tags)
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="nextra-container") or soup.body
        
        if not main_content:
            return ""
            
        # Clean up unwanted elements
        for script in main_content(["script", "style", "nav", "header", "footer"]):
            script.decompose()
            
        return main_content.get_text(separator="\n", strip=True)
    except Exception as e:
        print(f"  ⚠️ Failed to fetch {url}: {e}")
        return ""


def summarize_docs(api_key: str, pages_data: dict) -> str:
    """Ask Claude to extract the most useful technical info (endpoints, code snippets) into a clean context doc."""
    if not pages_data:
        return "No ScrapeBadger technical documentation provided."
        
    client = anthropic.Anthropic(api_key=api_key)
    
    compiled_docs = ""
    for title, content in pages_data.items():
        doc_url = DOCS_PAGES.get(title, "")
        compiled_docs += f"\n\n--- PAGE: {title} (URL: {doc_url}) ---\n{content[:5000]}" # Cap each at 5k chars roughly
        
    prompt = f"""
You are preparing technical context for a blog writer who is writing an article about: "{TOPIC}"
They need specific API references, endpoints, parameters, and features of the ScrapeBadger API to mention in the blog.

Here is the raw text scraped from the relevant ScrapeBadger documentation pages:
{compiled_docs}

Extract the most critical API endpoints, features, and code examples from this documentation that are directly relevant to the topic "{TOPIC}".
Format the output as a clean, concise Reference Guide (Markdown). Include the exact endpoint paths (like /v1/twitter/...) and brief descriptions of what they do.
CRITICAL: Include the exact URL for every endpoint/feature you mention so the blog writer knows what to link to!
Do not write the blog post. Just write the technical reference sheet.
"""

    print("🧠 Summarizing technical info for Blog Writer...")
    
    keys = load_keys()
    model_name = keys.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    
    message = client.messages.create(
        model=model_name,
        max_tokens=2000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text


def main():
    print(f"\n📚 ScrapeBadger Docs Agent Starting\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    keys = load_keys()
    api_key = keys.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY not found. Skipping Docs Agent.")
        return

    load_docs_pages_from_sitemap()
    load_inputs_from_sheet()
    
    # 1. Decide what to scrape
    selected_titles = select_relevant_pages(api_key)
    
    if not selected_titles:
        print("  ℹ️ Claude decided no specific docs pages are strictly required for this topic.")
        with open(OUTPUT_FILE, "w") as f:
            f.write("No specific ScrapeBadger technical documentation appended for this topic.")
        return
        
    print(f"  ✅ Selected {len(selected_titles)} relevant pages:")
    for t in selected_titles:
        print(f"     - {t}")
        
    # 2. Fetch the pages
    pages_data = {}
    for title in selected_titles:
        url = DOCS_PAGES[title]
        print(f"  🌐 Fetching {url}...")
        content = fetch_page_text(url)
        if content:
            pages_data[title] = content
            
    # 3. Summarize into a tech reference
    docs_summary = summarize_docs(api_key, pages_data)
    
    # 4. Save to .tmp/docs_context.txt
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== SCRAPEBADGER OFFICIAL DOCS CONTEXT ===\n\n{docs_summary}")
        
    print(f"\n📄 Docs context saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
