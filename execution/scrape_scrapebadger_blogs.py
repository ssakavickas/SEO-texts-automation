"""
scrape_scrapebadger_blogs.py

Dynamically discovers ALL blog posts from scrapebadger.com via sitemap.xml
and saves them as plain text files in .tmp/examples/ for Claude few-shot context.

When new posts are added to the blog, just re-run this script — it will detect
them automatically via the sitemap and update the examples directory.

Usage:
    python3 execution/scrape_scrapebadger_blogs.py
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR  = os.path.join(BASE_DIR, ".tmp", "examples")
SITEMAP_URL = "https://scrapebadger.com/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def discover_blog_posts() -> list[tuple[str, str]]:
    """Parse sitemap.xml to find all /blog/ post URLs automatically."""
    print(f"Discovering posts from {SITEMAP_URL}...")
    response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "xml")
    posts = []

    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        # Match only blog post URLs (not the /blog index itself)
        if re.match(r"https://scrapebadger\.com/blog/.+", url):
            slug = url.rstrip("/").split("/")[-1]
            safe_name = re.sub(r"[^a-z0-9_-]", "_", slug.lower())[:60]
            posts.append((safe_name, url))

    print(f"  Found {len(posts)} blog post(s).\n")
    return posts


def extract_article_text(html: str) -> str:
    """Extract clean readable text from a blog post page."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()

    article = (
        soup.find("article") or
        soup.find("main") or
        soup.find(class_=re.compile(r"post|article|content|blog", re.I)) or
        soup.body
    )

    lines = list(article.stripped_strings) if article else []
    text = "\n".join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def scrape_post(name: str, url: str) -> bool:
    print(f"Scraping: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        text = extract_article_text(response.text)

        if len(text) < 200:
            print(f"  ⚠️  Content too short ({len(text)} chars) — may be JS-rendered. Skipping.")
            return False

        out_path = os.path.join(OUTPUT_DIR, f"{name}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"SOURCE: {url}\n\n")
            f.write(text)

        print(f"  ✅ Saved {len(text):,} chars → {name}.txt")
        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output: {OUTPUT_DIR}\n")

    posts = discover_blog_posts()

    if not posts:
        print("No blog posts found. The page may be JS-rendered.")
        return

    success = 0
    for name, url in posts:
        ok = scrape_post(name, url)
        if ok:
            success += 1
        time.sleep(1)

    print(f"\nDone: {success}/{len(posts)} posts saved to .tmp/examples/")
    print("Re-run this script whenever new posts are published.")


if __name__ == "__main__":
    main()
