## SEO Metadata
Primary Keyword: price tracking bot
Meta Title: How to Build a Price Tracking Bot in Python
Meta Description: Learn how to build a price tracking bot that scrapes prices, stores history, detects drops, and sends Slack alerts. A complete Python guide for any scale.


---

## LinkedIn Post
Most price tracking tutorials stop at "print the price to terminal." That's not a bot. That's a demo.

A real price tracking system has four distinct jobs: fetch data on a schedule, store it with timestamps, detect meaningful changes, and alert you when something is actually worth acting on. Most hobby scripts collapse these into one tangled mess, which is exactly why they break the moment a site updates a CSS class or starts rendering prices via JavaScript.

The architecture matters more than the code. Keep the scraping layer, storage layer, change detector, and alerting layer separate. That separation is what lets you swap BeautifulSoup for a scraping API without rewriting your alert logic. It's what lets you scale from 10 products to 10,000 without starting over.

A few things worth knowing before you build:

SQLite is enough for most projects. No server, no configuration, handles hundreds of thousands of records without complaint.

Comparing price drops against yesterday's price creates false positives. Use the earliest recorded price as your baseline.

The most dangerous failure mode is a silent one. The scraper runs, no errors appear, but the data is stale. Build monitoring around your monitoring.

And past around 500 products across multiple retailers, maintaining a DIY scraper becomes more expensive than just paying for a scraping API. The math shifts faster than most people expect.

The full guide, including working Python code for all four layers, is at scrapebadger.com

---

## Twitter Thread
A price scraper fetches prices.
A price tracking bot fetches, stores, detects drops, and alerts you.

Most tutorials build the first and call it the second.

Read the full guide: scrapebadger.com

---

# How to Build a Price Tracking Bot for E-commerce Websites

Most price tracking tutorials show you how to scrape a single Amazon product page and print the price to a terminal. That's fine for a five-minute demo. It's useless for anything you'd actually run.

A real price tracking bot has four distinct jobs: fetch product data on a schedule, store it with timestamps, detect meaningful changes, and alert you when something worth acting on happens. Each of those steps has its own failure modes. This guide covers all of them.

By the end, you'll have a working Python pipeline that monitors multiple product URLs, persists price history in SQLite, calculates drop percentages, and sends a Slack notification when a threshold is crossed. The same architecture scales from 10 products to 10,000 with straightforward modifications.

## The Architecture Before the Code

A price tracking bot isn't a single script — it's a small pipeline with four components, each with a single responsibility.

| Component | Responsibility |
|---|---|
| Scraper | Fetches current price, stock status, and product name from a URL |
| Storage | Persists price records with timestamps for historical comparison |
| Change detector | Compares current price against historical baseline, calculates drop % |
| Alerting | Notifies you when a threshold is crossed |

Thinking in layers matters because this is where most hobby scripts fail. They mix scraping logic with alerting logic, have no storage, and break the moment the site changes a CSS class. Keeping concerns separate means you can swap out the scraper (say, from BeautifulSoup to a scraping API) without touching the alert logic.

## The Scraping Layer: Where Most Bots Break

The scraping layer is where you'll spend the most debugging time. The problem isn't writing the initial scraper — it's keeping it working.

E-commerce sites are actively hostile to scrapers. Amazon runs thousands of A/B tests. Prices are often rendered client-side via JavaScript. CSS selectors that work today break when a site redesigns. Anti-bot systems detect headless browsers, unusual request patterns, and datacenter IP ranges.

The two realistic approaches:

**BeautifulSoup + requests** works for static pages and simpler retailers. Fast, cheap, and easy to write. Breaks the moment JavaScript rendering is involved or anti-bot measures are in place.

**A scraping API** handles the infrastructure — proxy rotation, JavaScript rendering, request pacing, CAPTCHA solving — and returns structured data. More expensive per call, but the maintenance burden stays on the provider's side, not yours.

For a production bot tracking a watchlist across multiple retailers, a scraping API is almost always the right choice. The time you'd spend maintaining a headless browser setup for Amazon alone exceeds the cost of the API within a week.

Here's the minimal scraping function you'd write using an HTTP-based approach:

```python
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_price(url: str, css_selector: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    element = soup.select_one(css_selector)

    if not element:
        raise ValueError(f"Price element not found at {url}")

    # Strip currency symbols and commas
    raw = element.get_text(strip=True)
    price_text = raw.replace("$", "").replace(",", "").replace("£", "").replace("€", "")

    return {
        "url": url,
        "price": float(price_text),
        "timestamp": datetime.now().isoformat(),
    }
```

In practice, you'll need a per-site `css_selector` because Amazon, eBay, and Walmart all structure their price elements differently. Store these in a config file alongside your product URLs.

**The honest constraint:** This approach works on simple retail pages. For anything with JavaScript rendering, you'll either need a headless browser (Playwright or Selenium) or a service that handles that for you. The CSS selector approach also requires manual updates when sites change their structure — which they will.

## The Storage Layer: SQLite Is Enough

For most price tracking bots, SQLite is the right database. It's a single file, no server required, handles hundreds of thousands of records without issues, and is supported by Python's standard library. You don't need Postgres until you're tracking millions of price points with concurrent access.

```python
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "prices.db"

def setup_database():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            url     TEXT UNIQUE NOT NULL,
            name    TEXT,
            selector TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER REFERENCES products(id),
            price       REAL NOT NULL,
            recorded_at TEXT NOT NULL
        )
    """)

    con.commit()
    con.close()
```

Two tables. `products` stores what you're tracking. `price_history` is an append-only log of every price observation with a timestamp. Never delete historical records — you'll want them for trend analysis.

When inserting a new price observation:

```python
def record_price(url: str, price: float, timestamp: str):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    cur.execute("SELECT id FROM products WHERE url = ?", (url,))
    row = cur.fetchone()

    if row:
        product_id = row[0]
        cur.execute(
            "INSERT INTO price_history (product_id, price, recorded_at) VALUES (?, ?, ?)",
            (product_id, price, timestamp)
        )
        con.commit()

    con.close()
```

## The Change Detector: What "Price Drop" Actually Means

This is the part most tutorials skip. A price change isn't automatically worth alerting on. A $0.01 fluctuation is noise. A 15% drop on a product you're tracking for procurement purposes is a real signal.

Two thresholds worth setting explicitly:

- **Minimum drop percentage** (e.g., <span style="color: #2D6A4F; font-weight: bold;">5%</span> for general tracking, <span style="color: #2D6A4F; font-weight: bold;">10–15%</span> for high-value items)
- **Baseline price** — use the earliest recorded price, not yesterday's price, to detect real drops rather than oscillation

```python
def get_price_drop(url: str) -> dict | None:
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    cur.execute("SELECT id FROM products WHERE url = ?", (url,))
    row = cur.fetchone()
    if not row:
        con.close()
        return None

    product_id = row[0]

    cur.execute(
        """
        SELECT price FROM price_history
        WHERE product_id = ?
        ORDER BY recorded_at ASC
        LIMIT 1
        """,
        (product_id,)
    )
    earliest = cur.fetchone()

    cur.execute(
        """
        SELECT price, recorded_at FROM price_history
        WHERE product_id = ?
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        (product_id,)
    )
    latest = cur.fetchone()
    con.close()

    if not earliest or not latest:
        return None

    earliest_price = earliest[0]
    current_price, recorded_at = latest

    if earliest_price == 0:
        return None

    drop_pct = (earliest_price - current_price) / earliest_price * 100

    return {
        "url": url,
        "earliest_price": earliest_price,
        "current_price": current_price,
        "drop_pct": round(drop_pct, 2),
        "recorded_at": recorded_at,
    }
```

If `drop_pct` is negative, the price went up. If it exceeds your threshold, it's worth alerting on.

## The Alerting Layer: Slack Webhooks

Slack is the fastest path to useful alerts. A simple webhook POST means you get notifications in a channel your team already watches, with no email configuration required.

```python
import requests
import os

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

def send_price_alert(data: dict):
    if not SLACK_WEBHOOK:
        print("SLACK_WEBHOOK_URL not set — skipping alert")
        return

    message = (
        f":chart_with_downwards_trend: *Price Drop Detected*\n"
        f"URL: {data['url']}\n"
        f"Was: *${data['earliest_price']:.2f}*  →  Now: *${data['current_price']:.2f}*\n"
        f"Drop: *{data['drop_pct']}%*\n"
        f"Recorded: {data['recorded_at']}"
    )

    try:
        response = requests.post(
            SLACK_WEBHOOK,
            json={"text": message},
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Alert failed: {e}")
```

The `timeout=10` is not optional. A slow Slack response will block your entire check cycle if you skip it.

## Wiring It Together: The Main Loop

```python
import asyncio
import os
from pathlib import Path

PRODUCTS = [
    {
        "url": "https://example-shop.com/product/widget-pro",
        "name": "Widget Pro",
        "selector": "span.price"
    },
    {
        "url": "https://another-retailer.com/items/gadget-x",
        "name": "Gadget X",
        "selector": "div.product-price"
    },
]

PRICE_DROP_THRESHOLD = 5.0  # Alert if price drops >= 5%

def run_price_check():
    setup_database()
    
    for product in PRODUCTS:
        try:
            result = scrape_price(product["url"], product["selector"])
            record_price(result["url"], result["price"], result["timestamp"])

            drop_data = get_price_drop(result["url"])
            if drop_data and drop_data["drop_pct"] >= PRICE_DROP_THRESHOLD:
                send_price_alert(drop_data)
                
        except Exception as e:
            print(f"Error processing {product['url']}: {e}")
            # Log and continue — don't let one failure block the rest

if __name__ == "__main__":
    run_price_check()
```

Each product is processed independently. A failure on one URL doesn't abort the rest of the run. Errors are logged and the loop continues.

## Scheduling: Cron or a Schedule Library

Two practical options:

**Cron** (Linux/macOS) — reliable, no extra dependencies, runs whether or not you have a Python process running:

```bash
# Check prices every 6 hours
0 */6 * * * /path/to/.venv/bin/python /path/to/price_tracker.py >> /path/to/tracker.log 2>&1
```

**`schedule` library** — useful if you want to keep everything in Python:

```python
import schedule
import time

schedule.every(6).hours.do(run_price_check)

while True:
    schedule.run_pending()
    time.sleep(60)
```

For most setups, cron is more reliable. The `schedule` loop requires a process to stay alive. If it crashes, you stop getting data and won't know until you notice a gap.

## Common Failure Modes

| Failure | Symptom | Fix |
|---|---|---|
| CSS selector breaks | Price not found, `ValueError` | Inspect the live page, update selector in config |
| IP blocked | Empty response or CAPTCHA page | Rotate user-agent, add delay between requests, or use a scraping API |
| JavaScript-rendered price | Selector exists but returns empty string | Switch to Playwright or a scraping API |
| Silent data gaps | No errors, but price history has holes | Add a check: if zero results in last N hours, log a warning |
| Alert fatigue | Too many notifications | Raise the threshold or filter by minimum absolute price change |

The most dangerous failure is a silent one — the scraper runs without errors but returns stale or incomplete data. Build monitoring around your monitoring: alert if a product hasn't had a price recorded in the expected interval.

## Practical Decisions at Different Scales

If you're tracking <span style="color: #2D6A4F; font-weight: bold;">under 50 products</span>, a single cron job with synchronous scraping is fine. Run every 4–6 hours, keep the code simple.

If you're tracking <span style="color: #2D6A4F; font-weight: bold;">50–500 products</span>, move to async scraping with `asyncio` to parallelize requests. Add per-domain rate limiting so you don't hammer a single site.

Above <span style="color: #2D6A4F; font-weight: bold;">500 products</span>, a scraping API becomes essentially mandatory for sites with anti-bot protection. The maintenance cost of keeping a DIY scraper reliable across that many URLs and multiple retailers outweighs the per-request cost difference.

The same trade-off applies when choosing between building and buying your scraping infrastructure — if you're evaluating that decision for a related project, the breakdown in our [build vs. buy comparison for scraping infrastructure](https://scrapebadger.com/blog/build-vs-buy-should-you-build-your-own-twitter-scraper) is worth reading, as the economics translate directly.

For the data storage layer, once you've outgrown SQLite, the migration path is straightforward. Our guide to [storing scraped data in PostgreSQL](https://scrapebadger.com/blog/how-to-store-twitter-data-in-postgresql) covers the schema patterns that hold up as data volume grows.

## Extensions Worth Adding

Once the core pipeline is running, these are the upgrades that actually matter:

- **Lowest price tracking** — store the historical minimum per product separately so you can display "X% above all-time low"
- **Stock status tracking** — a price drop on an out-of-stock item isn't actionable. Add an `in_stock` boolean to every price record
- **Per-product thresholds** — different products warrant different sensitivity. A $5 notebook drop and a $200 laptop drop require different thresholds
- **Weekly digest** — instead of per-event alerts, a weekly summary of price movements across your full watchlist is often more useful for purchasing decisions

---

## FAQ

**What's the simplest way to build a price tracking bot in Python?**

The minimal version is: a `requests` + `BeautifulSoup` scraper, a SQLite database for storage, and a Slack webhook for alerts. That's it. The complexity only grows when you add multiple retailers, JavaScript-rendered pages, or high product volumes. Start with a working single-site scraper before building anything more.

**How often should a price tracking bot check prices?**

It depends on the type of product and the retailer. For most categories, every 4–6 hours is enough — flash sales typically run for hours, not minutes. Checking every 15 minutes is only worthwhile for highly volatile categories like electronics during major sales events. More frequent checks mean more infrastructure cost and more exposure to rate limiting.

**How do I avoid getting blocked when scraping e-commerce sites?**

Use a realistic `User-Agent` header, add random delays between requests (1–3 seconds), and don't scrape from a datacenter IP for large volumes. For serious tracking at scale, proxy rotation via a managed service is the practical solution. Some sites also have official product data APIs — check whether that's available before building a scraper.

**What database should I use for storing price history?**

SQLite is the right starting point for most projects. It requires no server, handles hundreds of thousands of records comfortably, and is fully supported by Python's standard library. Migrate to PostgreSQL when you need concurrent write access from multiple processes or are storing more than a few million records.

**How do I calculate a meaningful price drop percentage?**

Use the earliest recorded price as your baseline, not yesterday's price. Comparing against yesterday creates false positives from normal price oscillation. The formula is `(baseline_price - current_price) / baseline_price * 100`. Set a minimum threshold — typically 5% for general use — to filter out noise.

**What's the difference between a price scraper and a price tracking bot?**

A scraper is a one-shot tool that extracts current prices on demand. A price tracking bot is a persistent pipeline: it scrapes on a schedule, stores history, compares against baselines, and triggers alerts when conditions are met. The scraper is one component of the bot. Most tutorials teach you to build a scraper and call it a bot.

**How do I handle sites where prices are loaded by JavaScript?**

BeautifulSoup can't execute JavaScript, so it sees an empty price element. Your options are: use Playwright or Selenium to render the page before scraping, or use a scraping API that handles JavaScript rendering for you. For a multi-site tracker, a scraping API is usually the more practical choice — maintaining a headless browser setup per retailer becomes expensive quickly in both time and compute.