# How to Scrape Vinted Listings Automatically

Vinted doesn't offer a public API. If you want structured data — prices, item descriptions, seller info, category filters — you have to go get it yourself. That means scraping.

The good news is that most Vinted listing pages are publicly accessible. You don't need an account to browse search results. The session-based complexity only kicks in when you need to access user-specific data, persist filters, or avoid getting rate-limited mid-crawl.

This guide covers how to scrape Vinted listings in practice: what the data looks like, how Vinted's session model works, which tools to use, and where pipelines typically break.

## What "Scraping Vinted" Actually Means

There are two distinct things people mean when they say they want to scrape Vinted:

- **Listing data** — item titles, prices, sizes, brands, photos, condition, timestamps, seller usernames
- **Catalog-level data** — bulk extraction across categories, search results, filtering by price range or location

For most use cases (price tracking, resale analytics, deal alerts), you want listing data from search results. Vinted's search is URL-parameter driven, which makes it predictable to paginate systematically.

## How Vinted's Session Model Works

Vinted serves most catalog pages without requiring login. But it does use session cookies to track request patterns, apply rate limits, and serve localized content. If you hammer requests from a single IP without session state, you'll get blocked or start seeing degraded responses — empty results, redirects, or CAPTCHAs.

The practical implication: you need to initialize a session before scraping, and you need to maintain it across requests.

Here's what that flow looks like:

<span style="color: #2D6A4F; font-weight: bold;">1. Initialize session → 2. Set headers (User-Agent, Accept-Language) → 3. Make search request → 4. Paginate with cursor/offset → 5. Parse and export</span>

The session cookie that matters most is the one Vinted sets when you first visit the site. Grab it, persist it, and include it in every subsequent request. Without it, you're scraping as an anonymous bot with no session context — and Vinted's infrastructure treats that differently.

## Scraping Vinted Listings with Python

For simple listing extraction, `requests` + `BeautifulSoup` or direct JSON parsing is the right tool. Vinted's search endpoint returns structured JSON in many cases, which means you don't even need HTML parsing for the core fields.

### Step 1: Set Up Your Environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install requests beautifulsoup4
pip freeze > requirements.txt
```

### Step 2: Initialize a Session and Fetch Listings

Vinted's public search uses a URL pattern like:

```
https://www.vinted.com/api/v2/catalog/items?search_text=nike&catalog_ids=&order=newest_first&page=1&per_page=96
```

The key parameters:

| Parameter | Description | Example |
|---|---|---|
| `search_text` | Keyword filter | `nike`, `levi`, `zara` |
| `catalog_ids` | Category ID (optional) | `5` (men's clothing) |
| `order` | Sort order | `newest_first`, `price_low_to_high` |
| `page` | Page number | `1`, `2`, `3` |
| `per_page` | Items per page | `96` (max observed) |
| `price_from` | Minimum price filter | `5` |
| `price_to` | Maximum price filter | `50` |

Here's the minimal working scraper:

```python
import requests
import json
import time
import random
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.vinted.com/",
}

def init_session() -> requests.Session:
    """
    Initialize a session by visiting the homepage first.
    This picks up the session cookie Vinted sets on first visit.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # Prime the session — this sets cookies we'll need for subsequent API calls
    session.get("https://www.vinted.com/", timeout=10)
    time.sleep(random.uniform(2, 4))
    return session

def fetch_listings(
    session: requests.Session,
    query: str,
    page: int = 1,
    per_page: int = 96
) -> list[dict]:
    """
    Fetch a single page of Vinted listings for a given search query.
    Returns a list of normalized item dicts.
    """
    url = "https://www.vinted.com/api/v2/catalog/items"
    params = {
        "search_text": query,
        "order": "newest_first",
        "page": page,
        "per_page": per_page,
    }

    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    items = data.get("items", [])
    return items

def normalize(item: dict) -> dict:
    """
    Flatten a raw Vinted item object into a stable, exportable schema.
    Safe defaults for all fields.
    """
    return {
        "item_id":      str(item.get("id") or ""),
        "title":        str(item.get("title") or ""),
        "price":        str(item.get("price") or ""),
        "currency":     str(item.get("currency") or ""),
        "brand_title":  str(item.get("brand_title") or ""),
        "size_title":   str(item.get("size_title") or ""),
        "condition":    str(item.get("status") or ""),
        "url":          str(item.get("url") or ""),
        "photo_url":    str((item.get("photo") or {}).get("url") or ""),
        "seller_id":    str((item.get("user") or {}).get("id") or ""),
        "seller_login": str((item.get("user") or {}).get("login") or ""),
        "created_at":   str(item.get("created_at_ts") or ""),
    }

if __name__ == "__main__":
    session = init_session()
    raw_items = fetch_listings(session, query="nike air max", page=1)

    for item in raw_items[:5]:
        print(json.dumps(normalize(item), indent=2))
```

Run it:

```bash
python scrape_vinted.py
```

If you see structured JSON output with titles, prices, and URLs, the session initialization worked. If you get a `403` or empty `items` list, the session cookie wasn't picked up correctly — add a longer delay after the homepage request and retry.

### Step 3: Paginate Across Multiple Pages

Single-page scraping is a prototype. Real extraction means iterating across pages until you've collected what you need.

```python
import csv

CSV_COLUMNS = [
    "item_id", "title", "price", "currency", "brand_title",
    "size_title", "condition", "url", "photo_url",
    "seller_id", "seller_login", "created_at",
]

def scrape_to_csv(query: str, max_pages: int, out_path: str):
    session = init_session()
    seen_ids: set[str] = set()

    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for page in range(1, max_pages + 1):
            print(f"Fetching page {page}...")
            try:
                raw_items = fetch_listings(session, query=query, page=page)
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break

            if not raw_items:
                print("No more items. Stopping.")
                break

            new_count = 0
            for item in raw_items:
                row = normalize(item)
                if not row["item_id"] or row["item_id"] in seen_ids:
                    continue
                seen_ids.add(row["item_id"])
                writer.writerow(row)
                new_count += 1

            print(f"  → {new_count} new items (total seen: {len(seen_ids)})")

            # Human-like delay between pages
            time.sleep(random.uniform(3, 7))

    os.replace(tmp_path, out_path)
    print(f"Done. Saved to {out_path}")

if __name__ == "__main__":
    scrape_to_csv(
        query="levi 501",
        max_pages=10,
        out_path="output/vinted_listings.csv",
    )
```

The atomic write (`os.replace`) ensures you never end up with a half-written CSV if the job dies mid-run. Treat your output schema as a contract — it prevents half your future bugs.

## Where Vinted Scraping Breaks

Most Vinted scrapers fail for a handful of predictable reasons:

**Session expiry.** Vinted's session cookies are not permanent. For long-running jobs, you may need to reinitialize the session partway through. Add a re-init check if you're running for more than 30–60 minutes.

**IP-level rate limiting.** If you run back-to-back jobs from the same IP, Vinted's infrastructure starts throttling or redirecting. Use residential proxies for sustained extraction, and always add delays between requests. The `random.uniform(3, 7)` pattern above is a minimum — bump it up for larger jobs.

**Response shape changes.** Vinted has changed its API response structure before. Defensive normalization (the `or ""` defaults in `normalize()`) prevents your pipeline from crashing on missing fields, but you should still log warnings when expected fields are absent.

**Geo-specific behavior.** Vinted operates across multiple markets (FR, DE, UK, NL, etc.) with different subdomain structures. `vinted.com`, `vinted.fr`, `vinted.de` are separate endpoints. If you need cross-market data, you'll need separate sessions per domain.

**JavaScript-rendered content.** The JSON API endpoint works for catalog/search pages. If you need individual item detail pages and they start rendering client-side, you'll need Playwright or Puppeteer. For most listing-level extraction, the API endpoint is sufficient and significantly faster.

## Tool Comparison for Vinted Scraping

| Approach | Complexity | Speed | Handles JS | Best For |
|---|---|---|---|---|
| `requests` + JSON API | Low | Fast | No | Catalog, search results, bulk listing extraction |
| `requests` + BeautifulSoup | Low | Fast | No | HTML fallback when JSON API changes |
| Playwright / Puppeteer | High | Slow | Yes | Item detail pages, login-required content |
| Scrapy | Medium | Very fast | No | Large-scale crawls with built-in throttling |
| ScrapeBadger | Low | Fast | Yes | Managed extraction without infrastructure overhead |

For most Vinted use cases, `requests` against the JSON API is the right starting point. If you're running at scale or hitting anti-bot measures consistently, [ScrapeBadger](https://scrapebadger.com/sdks) handles proxy rotation, session management, and rate limiting as part of the service — so you can focus on the data rather than the infrastructure.

## What You Can Build With This Data

Vinted listing data is useful in several concrete ways:

- **Price tracking** — monitor how prices shift for a specific brand or category over time. Useful for knowing when to buy or sell.
- **Resale opportunity detection** — find underpriced items by brand/condition/size before they get bought. Combine with alerting logic to surface deals in real time.
- **Market research** — understand what's actually available in a category, average price points, and what conditions sell fastest.
- **Inventory monitoring** — if you're a seller, track what competitors are listing, at what prices, and how quickly items move.

If you're curious about the broader landscape of what's possible with scraped data, the [web scraping use cases guide](https://scrapebadger.com/blog/how-web-scraping-can-help-your-business-10-use-cases-with-real-results) covers concrete examples across industries.

## FAQ

**Does Vinted have an official public API?**

No. Vinted does not offer a public API for third-party developers. The `api/v2` endpoints used in this guide are internal endpoints that the Vinted frontend uses. They work for scraping purposes but are not officially documented or guaranteed to be stable.

**Do I need to log in to scrape Vinted listings?**

For public catalog and search data, no. Most listing pages are accessible without authentication. You do need to initialize a session (to pick up the session cookie Vinted sets on first visit), but that doesn't require an account. Login is only required for user-specific data like saved items, messages, or account details.

**Why am I getting empty results or 403 errors?**

Most commonly: your session wasn't initialized correctly, or you're making requests too fast from the same IP. Start by adding a delay after the homepage request in `init_session()`. If 403 errors persist, you likely need a proxy — Vinted's infrastructure detects and blocks datacenter IP ranges.

**How do I scrape across multiple pages without getting blocked?**

Use randomized delays between requests (`random.uniform(3, 7)` seconds minimum), reinitialize your session if it's been running more than an hour, and cap the number of pages per run. Running smaller batches more frequently is more reliable than trying to extract everything in one shot. If you're collecting more than a few thousand items per day, residential proxies are essentially required.

**Is scraping Vinted legal?**

This depends on your jurisdiction, what data you're collecting, and how you're using it. Vinted's terms of service prohibit automated scraping. You should review both the ToS and applicable laws (especially GDPR if you're in Europe, since seller profiles can contain personal data). Collecting publicly visible listing data for personal research is a different situation from commercial redistribution of user data. When in doubt, consult legal advice specific to your use case.

**What's the difference between scraping via the JSON API vs. parsing HTML?**

The JSON API endpoint (`/api/v2/catalog/items`) returns structured data directly — no HTML parsing required. It's faster, more stable, and gives you cleaner fields. HTML scraping is a fallback for when the API changes structure or when you need data only available on the rendered page. Start with the JSON API and only drop down to HTML parsing when necessary.

**Can I scrape Vinted listings for multiple countries?**

Yes, but each market is a separate domain (`vinted.fr`, `vinted.de`, `vinted.co.uk`, etc.) with its own session state. You'll need to initialize a separate session per domain and handle the different currency/locale fields in your normalization logic.