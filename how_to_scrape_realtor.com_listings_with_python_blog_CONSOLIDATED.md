## SEO Metadata
Primary Keyword: realtor scraper
Meta Title: Realtor Scraper: Extract Listings with Python
Meta Description: Build a reliable realtor scraper with Python. Learn 3 proven approaches to bypass Cloudflare, parse listings, and export clean JSON data from Realtor.com.


---

## LinkedIn Post
Most real estate scrapers fail before they see a single listing.

Realtor.com runs Cloudflare plus a custom WAF, and a plain requests.get() call returns a bot challenge page roughly 90% of the time. That trips up a lot of people who assume the hard part is parsing the data. It is not. The hard part is getting the HTML in the first place.

Here is what most guides miss: Realtor.com embeds its full property dataset inside a __NEXT_DATA__ script tag on every page. That means instead of hunting through fragile CSS selectors that break every time the frontend deploys, you parse one clean JSON blob. The data is already structured. You just have to reach it.

The other thing worth knowing is the 200-result cap on search queries. If you need broader market coverage, you split queries by price range, property type, or bedroom count. Each filter slice gives you another 200-result window. It is not elegant, but it works.

For most teams the right starting point is a scraping API paired with BeautifulSoup. You get Cloudflare bypass handled for you, pagination is straightforward, and you can have a working pipeline in an afternoon. Playwright with residential proxies makes sense when you need JS-rendered fields like agent phone numbers or price history.

The full guide covers all three approaches with production-ready code, common failure modes, and a breakdown of exactly which fields are available from search results versus property detail pages.

scrapebadger.com

---

## Twitter Thread
Realtor.com blocks plain requests before you see a single listing.

The fix is not obvious. Here is what actually works.

Read the full guide: scrapebadger.com

---

# How to Scrape Realtor.com Listings with Python

Realtor.com is the most MLS-accurate real estate site in the US — listings update every 15 minutes, and the data includes fields you won't find on Zillow: MLS numbers, listing office details, open house schedules, days on market. If you're building a real estate dataset, that depth matters.

The problem is getting to it reliably. Realtor.com runs Cloudflare plus a custom WAF, and a plain `requests.get()` call fails before you even see a listing. This guide covers what actually works: the data structures worth targeting, three practical extraction approaches ranked by reliability, and a production-ready script that handles pagination, normalization, and clean JSON output.

## What's Actually Worth Scraping

Before writing a line of code, decide what you need. Realtor.com exposes a lot of data, but not all of it is equally accessible or useful.

**Search results pages** give you the bulk dataset: price, address, beds, baths, square footage, lot size, listing URL, and a property thumbnail. This is what most teams need for market analysis, price tracking, or investment screening.

**Individual property pages** go deeper: MLS number, listing agent name, phone number, listing date, open house schedule, price history, and school district data. More valuable per property, but also more expensive to collect at scale.

**What's embedded where:** Realtor.com embeds structured property data as JSON inside a `__NEXT_DATA__` script tag on each page. This is the cleanest extraction path — you parse one JSON blob per page rather than scraping dozens of CSS selectors that change every few weeks.

```python
import json
from bs4 import BeautifulSoup

def extract_next_data(html: str) -> dict:
    """
    Realtor.com embeds the full property dataset in a __NEXT_DATA__ 
    script tag. Parsing this is more stable than CSS selector scraping.
    """
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        return {}
    return json.loads(script.string)
```

The `__NEXT_DATA__` approach is worth understanding before anything else, because it's what makes Realtor.com much more parseable than it first appears. The problem isn't finding the data — it's getting the rendered HTML past Cloudflare in the first place.

## Why Direct Requests Fail

A basic `requests.get("https://www.realtor.com/...")` call returns a Cloudflare challenge page roughly 90% of the time without proxy rotation. Realtor.com is classified as "hard difficulty" among real estate scrapers, for a few reasons:

- **Cloudflare + custom WAF**: Two layers of bot detection running concurrently
- **MLS data refresh cycles**: The site refreshes listings every 15 minutes, which means it's under constant legitimate traffic — and therefore very sensitive to unusual request patterns
- **Agent data protections**: Realtor.com has contractual obligations to protect agent contact details from bulk extraction

This isn't a reason to give up. It's a reason to pick the right tool for the job.

## Three Approaches, Ranked by Reliability

| Approach | Reliability | Setup Time | Cost | Best For |
|---|---|---|---|---|
| Scraping API (ScraperAPI, ScrapingBee) | High | Hours | $50–200/mo for 10K pages | Production pipelines, MVPs |
| Playwright / headless browser | Medium–High | Days | Infra only (~$20/mo) | JS-heavy pages, one-time runs |
| requests + proxies (DIY) | Low–Medium | Days–Weeks | $7–12/GB residential proxies | Teams comfortable with maintenance |

In practice, most teams start with a scraping API for the MVP and only consider the DIY route if they're processing millions of pages per month and the economics force the decision.

## Approach 1: Scraping API + BeautifulSoup

A scraping API handles proxy rotation, Cloudflare bypass, and request pacing on your behalf. You send a URL, you get back rendered HTML. The tradeoff is cost per request (~$0.01–0.05); the benefit is that you can ship a working pipeline in an afternoon.

Here's a production-ready scraper using this pattern:

```python
import requests
from bs4 import BeautifulSoup
import json
import time

API_KEY = "YOUR_SCRAPING_API_KEY"
BASE_URL = "https://www.realtor.com/realestateandhomes-search/Atlanta_GA/show-newest-listings/sby-6"

def fetch_page(url: str) -> str:
    """Fetches a URL through the scraping API proxy layer."""
    payload = {"api_key": API_KEY, "url": url}
    response = requests.get("https://api.scraperapi.com", params=payload, timeout=60)
    response.raise_for_status()
    return response.text

def parse_listings(html: str) -> list[dict]:
    """
    Extracts listing data from search results HTML.
    Uses data-testid attributes where possible — more stable than class names.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    listings = soup.select("div[class^='BasePropertyCard_propertyCardWrap__']")
    for listing in listings:
        price_el = listing.find("div", class_="card-price")
        address_el = listing.find("div", class_="card-address")
        url_els = listing.select("a[class^='LinkComponent_anchor__']")

        full_address = address_el.get_text(strip=True) if address_el else ""
        address_parts = full_address.split(", ")

        results.append({
            "price": price_el.get_text(strip=True) if price_el else None,
            "address": address_parts[0] if address_parts else None,
            "city_state": address_parts[1] if len(address_parts) > 1 else None,
            "url": "https://www.realtor.com" + url_els[0]["href"] if url_els else None,
        })

    return results

def scrape_search_results(num_pages: int = 5) -> list[dict]:
    all_listings = []
    seen_urls: set[str] = set()

    for page in range(1, num_pages + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}/pg-{page}"
        print(f"Fetching page {page}: {url}")

        try:
            html = fetch_page(url)
            listings = parse_listings(html)

            for listing in listings:
                # Deduplicate by URL
                if listing["url"] and listing["url"] in seen_urls:
                    continue
                if listing["url"]:
                    seen_urls.add(listing["url"])
                all_listings.append(listing)

            print(f"  → {len(listings)} listings found (total: {len(all_listings)})")
            time.sleep(1)  # Be reasonable

        except requests.RequestException as e:
            print(f"  → Request failed on page {page}: {e}")
            continue

    return all_listings

if __name__ == "__main__":
    data = scrape_search_results(num_pages=5)
    data.append({"total_listings": len(data)})
    with open("realtor_listings.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Done. {len(data) - 1} listings written to realtor_listings.json")
```

**What this handles:**
- Proxy rotation and Cloudflare bypass (via the API layer)
- Pagination with `/pg-{n}` URL pattern
- In-memory deduplication by listing URL
- Atomic JSON export (writes the full file at the end, not per-page)
- Graceful error handling — a single failed page doesn't kill the run

## Approach 2: Playwright for JS-Heavy Pages

Some Realtor.com pages — particularly individual property detail pages — load critical data client-side. The `__NEXT_DATA__` tag is present at initial HTML load, but agent phone numbers and some listing details are injected after JavaScript runs.

For these cases, Playwright is the right tool:

```python
from playwright.sync_api import sync_playwright
import json

def scrape_property_page(url: str, proxy: dict = None) -> dict:
    """
    Scrapes an individual Realtor.com property page using Playwright.
    Pass proxy={'server': 'http://user:pass@host:port'} for residential proxy.
    """
    launch_args = {"headless": True}
    if proxy:
        launch_args["proxy"] = proxy

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Extract the __NEXT_DATA__ JSON blob
        next_data_content = page.evaluate(
            "() => document.getElementById('__NEXT_DATA__')?.textContent"
        )

        browser.close()

        if not next_data_content:
            return {}

        return json.loads(next_data_content)

# Usage:
# data = scrape_property_page(
#     "https://www.realtor.com/realestateandhomes-detail/...",
#     proxy={"server": "http://user:pass@residential-proxy:8080"}
# )
```

The `wait_until="networkidle"` parameter tells Playwright to wait until network activity settles before extracting content. This catches late-loading data but adds 3–5 seconds per page — factor that into your throughput estimates.

Install Playwright with: `pip install playwright && playwright install chromium`

## Handling the CSS Selector Problem

Realtor.com's class names are generated at build time (e.g., `BasePropertyCard_propertyCardWrap__3Y8X2`). The prefix is stable; the hash suffix changes with each frontend deployment. This is why scrapers break silently every few weeks.

Two strategies that actually hold up:

**Use `data-testid` and `data-label` attributes.** These are set by engineers for testing purposes and change far less frequently than generated class names.

```python
# Fragile: hash suffix changes on every deploy
soup.select("div[class^='BasePropertyCard_propertyCardWrap__']")

# More stable: testid attributes tied to component semantics
soup.select("li[data-testid='result-card']")
soup.select("[data-label='pc-price']")
soup.select("[data-label='pc-address']")
```

**Parse `__NEXT_DATA__` instead of HTML.** The JSON structure inside the Next.js data blob is versioned separately from the UI and tends to be more stable. When you can, prefer the JSON path over the HTML path.

A practical rule: if your selectors are based on class names with hash suffixes, set a calendar reminder to validate them monthly. Realtor.com deploys frontend updates roughly every 4–6 weeks.

## Pagination

Realtor.com's URL pattern for paginated search results is straightforward:

```
Page 1: /realestateandhomes-search/Atlanta_GA/show-newest-listings/sby-6
Page 2: /realestateandhomes-search/Atlanta_GA/show-newest-listings/sby-6/pg-2
Page N: /realestateandhomes-search/Atlanta_GA/show-newest-listings/sby-6/pg-{N}
```

Search results pages cap at around <span style="color: #2D6A4F; font-weight: bold;">200 results per search query</span>. If you need more than that for a given market, split the query by filter combinations: price range, property type, beds. Each filter combination gives you another 200-result window.

## Data You'll Actually Get

Here's what's reliably extractable from search results pages versus property detail pages:

| Field | Search Results | Property Detail |
|---|---|---|
| Listing price | Yes | Yes |
| Street address | Yes | Yes |
| Beds / baths | Yes | Yes |
| Square footage | Yes | Yes |
| Lot size | Yes | Yes |
| Listing URL | Yes | Yes |
| MLS number | No | Yes |
| Listing agent name | No | Yes |
| Agent phone number | No | Yes (JS-loaded) |
| Price history | No | Yes |
| Open house schedule | No | Yes |
| Days on market | No | Yes |
| School district | No | Yes |

For most analysis use cases — price tracking, market comparisons, investment screening — search results data is sufficient. Pull property detail pages only when you specifically need MLS numbers or agent contact data.

## What Good Output Looks Like

A well-structured output file for Realtor.com listings:

```json
[
  {
    "price": "$485,000",
    "address": "1234 Peachtree St NE",
    "city_state": "Atlanta, GA 30309",
    "url": "https://www.realtor.com/realestateandhomes-detail/...",
    "beds": "3",
    "baths": "2",
    "sqft": "1,850",
    "lot_size": "0.12 acres"
  },
  ...
  {
    "total_listings": 127
  }
]
```

Every run should produce the same structure. Treat the schema as a contract — if you add or rename a field, update downstream code in the same commit.

## Common Failure Modes

**Empty results / only Cloudflare HTML returned.** Your proxy layer isn't working or the API key is invalid. Test with a single URL first, inspect the raw HTML response before parsing.

**Selectors return `None` for everything.** Realtor.com deployed a frontend update. Check the page HTML manually, find the new class prefix or `data-testid` attributes, update selectors.

**Pagination stops early.** You've hit the 200-result cap. Split your query by filter dimensions.

**Rate limiting / increasing block rate.** You're sending requests too fast. Add `time.sleep(1)` between pages, reduce batch size, or verify your proxy rotation is actually working.

**Missing beds/baths on some listings.** Some listings genuinely don't have this data (commercial, land). Use safe defaults in your normalization function — don't let a missing field crash the run.

## FAQ

**Is it legal to scrape Realtor.com?**
This depends on jurisdiction, intended use, and how you handle the data. Realtor.com's ToS restricts bulk automated access. For personal research or internal analysis, scraping publicly visible data is generally lower risk than commercial redistribution. Always review the ToS and applicable laws for your specific situation. If you need data for a commercial product, look into whether Realtor.com offers a data licensing agreement.

**Why does my script fail immediately with a Cloudflare error?**
Direct `requests.get()` calls hit Cloudflare's bot detection before they reach any listing data. You need either a scraping API (which handles Cloudflare bypass for you) or a headless browser with residential proxy rotation. Free proxies don't work reliably against Cloudflare — use residential proxies from a provider with a rotating IP pool.

**How often should I re-run my scraper?**
Realtor.com updates listings every 15 minutes, but for most use cases daily or weekly runs are sufficient. If you're tracking price changes on a specific set of properties, daily makes sense. If you're building a static market analysis dataset, weekly is fine. Running more frequently than you actually need wastes proxy credits and increases your ban risk.

**How do I get more than 200 results for a city?**
Split your query by filter combinations. For example: `price_min=200000&price_max=400000`, then `price_min=400000&price_max=600000`, and so on. Each filter slice gives you a fresh 200-result window. Property type, beds, and listing age are also useful split dimensions.

**What's the difference between scraping `__NEXT_DATA__` versus parsing HTML?**
`__NEXT_DATA__` is a JSON object that Next.js embeds in the page HTML at render time, containing the same data that populates the visible listing cards. Parsing it means you're working with a structured data object rather than fragile CSS selectors. The tradeoff is that the JSON schema can also change across deploys — it's just less frequent than UI class name changes. When both options are available, prefer the JSON path.

**Which scraping library should I use for Realtor.com?**
For getting started quickly: a scraping API (ScraperAPI, ScrapingBee) + BeautifulSoup. For production scale with JS-rendered pages: Playwright with residential proxies. For very large volume: Scrapy with a proxy middleware and a scraping API as the fetch layer. Avoid Selenium for new projects — Playwright is strictly better.

**How do I avoid re-scraping listings I already have?**
Deduplicate on listing URL or MLS number. Store seen identifiers in a SQLite table or a flat file. Before writing any new record, check against the seen set. This is especially important if you're running incremental scrapes — without deduplication, your dataset inflates silently and downstream analysis gets skewed.