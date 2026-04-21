# How to Scrape Product Listings from Any E-commerce Website with Python

Most e-commerce scraping tutorials show you how to pull data from one specific site, with hardcoded selectors that break the moment the site updates its CSS. That's not a pipeline — that's a one-time script with an expiration date.

This guide covers how to build a scraper that works across e-commerce sites, handles the two main content types you'll encounter (static HTML and JavaScript-rendered storefronts), and holds up when sites push back. By the end, you'll have a working Python pipeline that extracts product names, prices, availability, and ratings — exportable to CSV or a database.

---

## What You're Actually Up Against

Before writing a single line of code, it helps to understand why e-commerce scraping fails more often than it should.

The problem isn't parsing HTML. That part is easy. The hard parts are:

**JS-rendered content.** A large percentage of modern storefronts — anything built on React, Vue, or similar — render product grids client-side. If you fetch the raw HTML with `requests`, you get a shell with no product data in it. You'll see `<div id="app"></div>` and nothing useful.

**Anti-bot systems.** Amazon uses its own detection stack. Cloudflare protects a significant portion of mid-tier retailers. DataDome is common on fashion and luxury sites. These systems fingerprint your requests and block scrapers that look like scrapers — which a basic `requests` call absolutely does.

**Pagination and lazy loading.** Product listings rarely fit on one page. Some sites use traditional `?page=2` URLs. Others use infinite scroll triggered by a scroll event. Both require different handling.

**Selector fragility.** CSS class names change. Sites A/B test layouts. A scraper that works today can fail silently next week because `.product-card` became `.product-tile`. You need defensive parsing with fallbacks, not hardcoded assumptions.

If you're [new to web scraping tools in general](https://scrapebadger.com/blog/web-scraping-for-beginners-the-only-tool-guide-you-need-in-2026), it's worth understanding the full landscape before diving into e-commerce specifically — the same infrastructure problems apply across all domains.

---

## The Two Approaches You Need to Know

### Static HTML Scraping (Requests + BeautifulSoup)

Works for: product pages and category listings that render fully server-side. Think older storefronts, smaller retailers, and sites that haven't migrated to SPAs yet.

The pattern is simple:

```python
import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
}

response = requests.get("https://example-shop.com/category/shoes", headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

products = []
for card in soup.find_all("div", class_="product-card"):
    name = card.find("h2", class_="product-name")
    price = card.find("span", class_="price")
    products.append({
        "name": name.get_text(strip=True) if name else None,
        "price": price.get_text(strip=True) if price else None,
    })

print(products)
```

A few things that matter here:

- **Always set a User-Agent header.** Without one, you're broadcasting that you're a bot.
- **Use `try/except` or conditional checks** for every field. Missing elements are normal — products without prices, listings without ratings. Don't let a single `None` crash your loop.
- **The class names above are placeholders.** Every site uses different ones. Inspect the actual HTML before writing selectors.

For pagination, check whether the site uses URL-based pages:

```python
for page in range(1, 6):
    url = f"https://example-shop.com/category/shoes?page={page}"
    response = requests.get(url, headers=headers)
    # parse as above
```

### JavaScript-Rendered Storefronts

For sites that load product data dynamically, you need a browser. The two main options are Selenium (older, more documentation) and Playwright (faster, cleaner API). Here's a minimal Playwright example:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example-shop.com/products")

    # Wait for product grid to load before extracting
    page.wait_for_selector(".product-grid")

    products = []
    for card in page.query_selector_all(".product-card"):
        name = card.query_selector(".product-name")
        price = card.query_selector(".price")
        products.append({
            "name": name.inner_text() if name else None,
            "price": price.inner_text() if price else None,
        })

    browser.close()
    print(products)
```

Install with `pip install playwright && playwright install chromium`.

The `wait_for_selector` call is critical. Without it, you're extracting from a half-loaded page and wondering why your data is empty.

---

## Using a Scraping API for Sites That Block You

Headless browsers work until a site deploys Cloudflare, Akamai, or DataDome. At that point, you're in an arms race you're going to lose. Browser fingerprinting is sophisticated enough to detect Playwright and Selenium regardless of what User-Agent you set.

The practical solution for production pipelines is to route requests through a scraping API that handles anti-bot bypass, proxy rotation, and JS rendering on its end. You get back clean HTML. You parse it. You're done.

[ScrapeBadger's web scraping endpoint](https://docs.scrapebadger.com/web-scraping/overview) at `POST https://scrapebadger.com/v1/web/scrape` handles this. The minimal call for a JS-heavy product listing page:

```python
import requests
from bs4 import BeautifulSoup

response = requests.post(
    "https://scrapebadger.com/v1/web/scrape",
    headers={
        "x-api-key": "YOUR_API_KEY",
        "Content-Type": "application/json"
    },
    json={
        "url": "https://example-shop.com/products",
        "format": "html",
        "render_js": True,
        "wait_for": ".product-grid",
        "anti_bot": True,
        "escalate": True,
        "country": "us"
    }
)

html = response.json()["content"]
soup = BeautifulSoup(html, "html.parser")

# Parse normally from here
```

What's happening with each parameter:

- `render_js: True` — runs the page in a full browser so JS-rendered products appear in the HTML
- `wait_for: ".product-grid"` — waits until the product grid is present before extracting, same logic as `wait_for_selector` in Playwright
- `anti_bot: True` — activates the anti-bot solver for protected sites
- `escalate: True` — automatically steps up from HTTP to browser to premium browser if earlier tiers get blocked. You only pay for the tier that succeeds.
- `country: "us"` — routes through US proxies, useful for geo-restricted pricing or regional product catalogs

For lazy-loaded pages where products appear as you scroll, add `wait_after_load`:

```python
json={
    "url": "https://example-shop.com/products",
    "render_js": True,
    "wait_after_load": 2000  # ms to wait after initial load
}
```

---

## Handling Pagination Programmatically

Whether you're using `requests` or a scraping API, pagination logic is the same: loop over pages, collect product links, scrape each one.

```python
import requests
from bs4 import BeautifulSoup

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://example-shop.com/category/laptops"
product_links = []

def fetch_page(url):
    resp = requests.post(
        "https://scrapebadger.com/v1/web/scrape",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json={"url": url, "format": "html", "render_js": True, "anti_bot": True}
    )
    return BeautifulSoup(resp.json()["content"], "html.parser")

# Collect product links across pages
for page in range(1, 6):
    url = f"{BASE_URL}?page={page}"
    soup = fetch_page(url)
    for link in soup.find_all("a", class_="product-link"):
        href = link.get("href")
        if href and href not in product_links:
            product_links.append("https://example-shop.com" + href)

print(f"Found {len(product_links)} products")
```

For infinite scroll pages, use `js_scenario` to simulate scrolling before extraction:

```python
json={
    "url": "https://example-shop.com/products",
    "render_js": True,
    "js_scenario": [
        {"type": "scroll", "direction": "down", "amount": 2000},
        {"type": "wait", "milliseconds": 1500},
        {"type": "scroll", "direction": "down", "amount": 2000},
        {"type": "wait", "milliseconds": 1500}
    ]
}
```

---

## AI Extraction: Skip the Selector Hunting

If you're scraping many different e-commerce sites and don't want to write site-specific CSS selectors for each one, the `ai_extract` option is worth knowing about. Instead of figuring out whether the price lives in `.product-action__price` or `.price-wrapper` or `[data-price]`, you describe what you want in plain language:

```python
json={
    "url": "https://example-shop.com/category/headphones",
    "format": "html",
    "render_js": True,
    "ai_extract": True,
    "ai_prompt": "Extract all products. For each product return: name, price, currency, rating, availability, and URL."
}
```

The response includes a structured `ai_extraction` field with the parsed data. This costs <span style="color: #2D6A4F; font-weight: bold;">+2 credits</span> on top of the base rendering cost, but it eliminates the selector maintenance problem entirely for multi-site pipelines.

---

## Normalizing and Exporting Product Data

Raw scraped data is inconsistent. Prices come back as `"$29.99"`, `"29,99 €"`, or `"From $25"`. Ratings might be `"4.5 out of 5"` or just `"4.5"`. Normalize before you store.

```python
import csv
import re

def normalize_product(raw: dict) -> dict:
    # Clean price — strip currency symbols and whitespace
    raw_price = raw.get("price") or ""
    price_clean = re.sub(r"[^\d.]", "", raw_price.replace(",", "."))

    return {
        "name": str(raw.get("name") or "").strip(),
        "price": float(price_clean) if price_clean else None,
        "currency": "USD",  # Set per-site if scraping internationally
        "rating": str(raw.get("rating") or "").strip() or None,
        "availability": str(raw.get("availability") or "").strip() or None,
        "url": str(raw.get("url") or "").strip(),
    }

# Write to CSV
CSV_COLUMNS = ["name", "price", "currency", "rating", "availability", "url"]

def export_to_csv(products: list, out_path: str):
    tmp = out_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for p in products:
            writer.writerow(normalize_product(p))
    import os
    os.replace(tmp, out_path)  # Atomic write — no partial CSVs
```

The atomic write pattern (write to `.tmp`, then rename) prevents half-written files if the process is interrupted. Same principle applies whether you're writing CSV or inserting into a database.

---

## Scraping Engine Selection: When to Use What

| Site Type | Engine | Cost Per Request | When to Use |
|---|---|---|---|
| Static HTML, no JS | HTTP (auto) | 1 credit | Small retailers, older storefronts |
| React/Vue/Angular storefront | Browser (`render_js: true`) | 5 credits | Most modern e-commerce sites |
| Cloudflare / DataDome protected | Premium Browser (via escalation) | 10 credits | Amazon, major fashion brands, luxury retail |
| AI-structured extraction needed | Browser + AI | 7 credits | Multi-site pipelines, LLM integration |

The <span style="color: #2D6A4F; font-weight: bold;">escalate: true</span> flag handles tier selection automatically. You don't need to know in advance which tier a site requires — ScrapeBadger steps up as needed and you pay for whatever tier actually worked.

---

## Common Failure Modes (and What to Do)

**Empty product grid.** The page loaded but the product HTML is absent. Usually means JS rendering wasn't enabled or `wait_for` fired too early. Add `wait_after_load: 2000` and check that your `wait_for` selector is actually present on the page.

**Partial data — some products missing fields.** Normal. Use `try/except` or conditional field access everywhere. Never assume a field exists.

**IP blocks / 403s.** Your requests are being identified and rejected. Switch to a scraping API with proxy rotation, or add `anti_bot: true` if already using one.

**Pagination stops working after page 3.** Some sites use session cookies for pagination. Use `session_id` to maintain a persistent session across requests:

```python
json={
    "url": f"https://example-shop.com/products?page={page}",
    "session_id": "my-scrape-session-001"
}
```

**Prices showing wrong currency or region.** Use the `country` parameter to route through proxies in the target region:

```python
json={
    "url": "https://example-shop.com/products",
    "country": "gb"  # Route through UK proxies for GBP pricing
}
```

---

## What This Looks Like in Production

If you're running this as a scheduled job — daily price monitoring, weekly catalog sync — the operational requirements are similar to any other data pipeline:

- **Cap each run.** Decide how many pages you're collecting per run. Unbounded jobs create unpredictable credit usage and long runtime.
- **Deduplicate by product URL or SKU.** Products reappear across pages. A product URL is a stable key for deduplication.
- **Log per run:** products collected, pages scraped, failures, runtime. Alert if output drops to zero — it usually means something broke, not that the store is empty.
- **Store raw HTML alongside parsed data.** When your selectors break (they will), you want to reprocess from stored HTML rather than re-scrape everything.

For a broader look at the real cost tradeoffs between building scraping infrastructure yourself versus using a managed API, [this comparison](https://scrapebadger.com/blog/scrapebadger-vs-diy-scraping-infrastructure-the-real-cost-comparison) is worth reading before you architect anything.

---

## FAQ

**What Python libraries do I need to scrape e-commerce product listings?**

For static sites: `requests` and `BeautifulSoup` (`beautifulsoup4`). For JS-rendered sites: `playwright` or `selenium`. For production pipelines that need anti-bot handling, route through a scraping API and use only `requests` to call it — the library handles rendering and proxies on its end.

**How do I scrape a site built with React or Vue?**

You need a headless browser to execute the JavaScript before extracting HTML. Use Playwright's `wait_for_selector()` or set `render_js: true` with a `wait_for` CSS selector when calling a scraping API. Never try to parse the raw HTML from a React app — you'll get nothing useful.

**How do I handle Cloudflare or other anti-bot protection?**

Don't try to bypass Cloudflare manually with headers or cookie manipulation — it's a time sink and the detection is significantly more sophisticated than User-Agent checks. Use a scraping API that handles anti-bot bypass natively, or set `anti_bot: true` with `escalate: true` in ScrapeBadger's [`/v1/web/scrape`](https://docs.scrapebadger.com/api-reference/endpoint/web-scraping/scrape) endpoint.

**How do I scrape product listings across multiple pages?**

If the site uses URL-based pagination (`?page=2`, `?pg=3`), loop over page numbers and collect product links before scraping each one. For infinite scroll, use `js_scenario` with scroll actions to trigger lazy-loaded content before extracting. Always deduplicate collected URLs — products can appear on multiple pages.

**Is it legal to scrape e-commerce websites?**

It depends on jurisdiction, the site's terms of service, and how you use the data. Scraping publicly visible product data for price research or catalog enrichment is common practice and generally considered acceptable. Scraping at volumes that affect site performance, scraping behind authentication, or redistributing scraped data commercially introduces legal risk. Always check `robots.txt` and the site's ToS, and consult legal advice for commercial applications at scale.

**How do I avoid duplicate products in my output?**

Use the product URL or SKU as a unique key. In-memory deduplication with a Python `set` works fine for a single run. For incremental jobs that run on a schedule, persist seen product URLs in a database or checkpoint file and check against it at the start of each run.

**How much does it cost to scrape 10,000 product pages?**

Using ScrapeBadger: static HTML pages cost <span style="color: #2D6A4F; font-weight: bold;">1 credit each</span> (10,000 credits total), JS-rendered pages cost <span style="color: #2D6A4F; font-weight: bold;">5 credits each</span> (50,000 credits), and anti-bot solver adds <span style="color: #2D6A4F; font-weight: bold;">+5 credits per request</span>. In practice, most catalogs mix static and dynamic pages, so the real number lands somewhere in between. Failed requests cost nothing.