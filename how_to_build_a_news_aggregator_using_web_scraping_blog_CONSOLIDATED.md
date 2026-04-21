## SEO Metadata
Primary Keyword: news scraping
Meta Title: Build a News Aggregator With News Scraping in Python
Meta Description: Learn how to build a reliable news scraping pipeline in Python. Parse multiple sources, deduplicate articles, and export clean data on a schedule.


---

## LinkedIn Post
Most people who build a news aggregator think the hard part is writing the parser. It isn't.

The hard part is building something that still works next Tuesday, when the first site quietly renames a CSS class, the second starts returning 403s, and the third syndicates the same Reuters story your other four sources already grabbed.

The pipeline breaks not because the code was wrong, but because it was written as if the web stays still.

The smarter approach is to stop thinking in scripts and start thinking in stages: fetch, parse, normalize, deduplicate, export. Each layer has one job. When something fails, you know exactly where to look. A fetch error and a schema mismatch are different problems with different fixes, and collapsing them into one tangled function means debugging both at once.

A few things that actually matter in practice: write source-specific parsers instead of one universal extractor, normalize URLs before deduplication or you'll miss obvious duplicates, and use an atomic write pattern when exporting so a mid-run crash doesn't corrupt your output file.

None of this is complicated. But the difference between a scraper that runs once and a pipeline you can trust on a schedule is almost entirely in these details.

If you want the full working code with schema design, deduplication logic, failure mode handling, and scheduling setup, the complete guide is at scrapebadger.com

---

## Twitter Thread
Your news scraper works great.
Until tomorrow, when the HTML changes.

Build it as a pipeline, not a script.
Fetch. Parse. Normalize. Deduplicate. Export.

Each stage fails independently. That matters.

Read the full guide: scrapebadger.com

---

# How to Build a News Aggregator Using Web Scraping

Most news aggregators people build start the same way: a quick script that grabs headlines from one site, dumps them into a file, and calls it done. Then they try to add a second source. Then a third. Then the first site changes its HTML structure, the second site starts blocking requests, and the whole thing falls apart over a weekend.

This guide is about building one that doesn't fall apart. Not a proof-of-concept — a small pipeline you could actually run on a schedule, across multiple sources, and trust to give you consistent output.

By the end, you'll have a working news scraper in Python that handles static pages, deals with the common failure modes, normalizes articles into a stable schema, deduplicates across sources, and exports to a format you can actually use downstream.

## What You're Actually Building

Before writing any code, it helps to think in terms of pipeline stages rather than one monolithic script.

The flow looks like this:

```
Source list → Fetch HTML → Parse articles → Normalize schema → Deduplicate → Export
```

Each stage has a single job. This matters because when something breaks — and it will — you want to know exactly which layer is the problem. Did the fetch fail? Did the parser return empty results? Did a schema field go missing? These are three different bugs with three different fixes.

For this guide, we'll scrape a few static news sources using `requests` and `BeautifulSoup`, normalize everything into a shared article schema, deduplicate by URL, and export to CSV. That's a production-viable foundation you can extend later.

## What Makes News Scraping Harder Than It Looks

The naive approach works once. The problems start when you run it again tomorrow.

**Site structure changes.** News sites redesign regularly. A CSS class you're targeting today — `class="article-title"` — may be gone next month. Without tests or monitoring, you find out when your CSV suddenly has zero rows and no error messages.

**Duplicate articles.** Major stories get syndicated. Reuters content shows up on a dozen outlets. If you scrape multiple sources without deduplication, your dataset fills up with copies of the same story and your downstream analysis gets skewed.

**Anti-bot defenses.** Static sites are usually fine with basic `requests`. But some news sites serve Cloudflare challenges, check User-Agent headers, or implement rate limiting. In practice, 50–70% of scrapers get blocked without any proxy rotation on high-traffic sites. For a news aggregator pulling from smaller, static sources this is less of an issue — but it's something to design around from the start.

**Schema inconsistency.** One site puts the author in a `<span class="byline">`. Another buries it in a metadata tag. A third doesn't publish author info at all. If your pipeline assumes uniform fields, it crashes on edge cases.

The fix for all of this is the same: treat each source as a separate extractor with its own parsing logic, normalize outputs into a shared schema, and build defensive defaults for every field.

## Setting Up the Environment

Keep this isolated. Dependency conflicts between projects are a real time sink.

```bash
mkdir news-aggregator
cd news-aggregator
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

pip install requests beautifulsoup4 lxml pandas
pip freeze > requirements.txt
```

Project structure:

```
news-aggregator/
  scraper.py
  sources.py
  output/
```

Create the output folder:

```bash
mkdir -p output
```

## Choosing Your Sources: Static vs. Dynamic Sites

Not all news sites are scrape-friendly with basic `requests`. Before writing a single parser, check whether the target site renders content server-side or client-side.

The simplest test: open the page source (`Ctrl+U` in most browsers) and search for a headline you can see on the page. If it's in the source HTML, the site is static — `requests` will work fine. If the source is mostly empty JavaScript scaffolding, you're dealing with a dynamic site that requires a headless browser like Playwright or Selenium.

| Site Type | Scraping Method | Complexity | Examples |
|---|---|---|---|
| Static HTML | requests + BeautifulSoup | Low | Reuters, AP News, many regional outlets |
| JavaScript-rendered | Playwright / Selenium | Medium-High | Some aggregators, SPA-based sites |
| API-based | Direct HTTP to JSON endpoint | Low (if public) | Some outlets expose RSS or JSON feeds |
| RSS feeds | feedparser or requests + XML parsing | Low | Most major publications |

For this guide, we're focusing on static HTML. It covers the majority of real-world news sources and keeps the tooling straightforward.

**Practical rule:** If a site has an RSS feed, use it. It's structured, stable, and usually exempt from anti-scraping measures. Parse RSS with `feedparser` and skip the HTML entirely. For sites without feeds, the static HTML approach below applies.

## The Core Scraper

Let's build a minimal working scraper first, then harden it.

### Step 1: Define a Shared Article Schema

Every article your pipeline produces should have the same fields, regardless of source. Missing fields get safe defaults — never `None` if you can avoid it.

```python
# scraper.py
from dataclasses import dataclass, field

@dataclass
class Article:
    title: str = ""
    url: str = ""
    source: str = ""
    published_at: str = ""
    summary: str = ""
    author: str = ""
```

Treat this schema as a contract. Any change to it has downstream consequences.

### Step 2: Fetch and Parse a Static Source

Here's a generic fetch-and-parse function. The `lxml` parser is faster than Python's built-in HTML parser and handles malformed markup more gracefully.

```python
import requests
from bs4 import BeautifulSoup
import time
import random

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def fetch_html(url: str, timeout: int = 10) -> BeautifulSoup | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None
```

Setting a `User-Agent` header that looks like a real browser cuts your block rate significantly on static sites. The `timeout` parameter prevents the script from hanging indefinitely on slow responses.

### Step 3: Write Source-Specific Extractors

Each news source gets its own extraction function. This is intentional — trying to write one universal parser that handles every site's HTML structure is how you end up with a fragile mess that breaks everywhere at once.

```python
def parse_hacker_news(soup: BeautifulSoup) -> list[Article]:
    """Extract articles from Hacker News front page."""
    if soup is None:
        return []

    articles = []
    for item in soup.find_all("tr", class_="athing"):
        title_cell = item.find("span", class_="titleline")
        if not title_cell:
            continue

        link_tag = title_cell.find("a")
        if not link_tag:
            continue

        articles.append(Article(
            title=link_tag.get_text(strip=True),
            url=link_tag.get("href", ""),
            source="Hacker News",
            published_at="",   # HN doesn't show dates on the list view
            summary="",
            author="",
        ))

    return articles
```

When you add a new source, you add a new function. Nothing else changes.

### Step 4: Normalize and Deduplicate

Raw URLs from different sources may differ in subtle ways — trailing slashes, UTM parameters, `http` vs `https`. Normalize before deduplicating.

```python
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """Strip query params and fragments, normalize scheme."""
    parsed = urlparse(url)
    normalized = parsed._replace(query="", fragment="")
    return urlunparse(normalized).rstrip("/").lower()

def deduplicate(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    unique = []
    for article in articles:
        key = normalize_url(article.url)
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append(article)
    return unique
```

### Step 5: Export to CSV

```python
import csv
import os

CSV_COLUMNS = ["title", "url", "source", "published_at", "summary", "author"]

def export_to_csv(articles: list[Article], out_path: str):
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for article in articles:
            writer.writerow({
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at,
                "summary": article.summary,
                "author": article.author,
            })
    os.replace(tmp_path, out_path)
    print(f"Exported {len(articles)} articles to {out_path}")
```

The atomic write pattern — write to `.tmp`, then rename — prevents partial CSV files if the script crashes mid-export. It's a small thing that saves you from corrupted output at the worst time.

### Step 6: Wire It Together

```python
def main():
    all_articles = []

    sources = [
        ("https://news.ycombinator.com/", parse_hacker_news),
        # Add more source tuples here:
        # ("https://example-news-site.com/", parse_example_news),
    ]

    for url, parser in sources:
        print(f"Fetching: {url}")
        soup = fetch_html(url)
        articles = parser(soup)
        print(f"  → {len(articles)} articles parsed")
        all_articles.extend(articles)

        # Be polite. Don't hammer sources back-to-back.
        time.sleep(random.uniform(1.5, 3.0))

    unique_articles = deduplicate(all_articles)
    print(f"After deduplication: {len(unique_articles)} articles")

    export_to_csv(unique_articles, "output/news.csv")

if __name__ == "__main__":
    main()
```

Run it:

```bash
python scraper.py
```

## Adding More Sources: The Pattern

Adding a second or third news source is straightforward. Inspect the target site's HTML using browser DevTools, identify the container elements for article cards, and write a new `parse_*` function following the same pattern.

A few things to check for each new source:
- Is the title in an `<h2>`, `<h3>`, or an `<a>` tag?
- Is the URL absolute (`https://...`) or relative (`/article/123`)?  If relative, prepend the base domain.
- Is there a date field? What format is it in?
- Does the site have an RSS feed you should use instead?

For relative URLs:

```python
from urllib.parse import urljoin

BASE_URL = "https://example-news-site.com"
full_url = urljoin(BASE_URL, relative_path)
```

## Common Failure Modes

| Problem | What it looks like | Fix |
|---|---|---|
| Parser returns empty list | No errors, CSV has only headers | Site changed HTML structure. Re-inspect with DevTools. |
| Blocked requests (403/429) | `HTTPError` in logs | Add `User-Agent` header, add delays between requests. |
| Duplicate articles | Inflated row counts, repeated titles | Normalize and deduplicate by URL before export. |
| Missing fields | Empty columns for some sources | Defensive defaults in `Article` dataclass + conditional extraction. |
| Malformed URLs | Relative paths in URL column | Use `urljoin()` for all URL extraction. |
| Script hangs | No output, no errors | Set `timeout` on every `requests.get()` call. |

## Scheduling the Aggregator

A script that only runs when you remember to run it isn't an aggregator — it's a command you occasionally type. Schedule it.

Using cron (Linux/macOS):

```bash
crontab -e
```

Add a line to run every hour:

```bash
0 * * * * /path/to/.venv/bin/python /path/to/news-aggregator/scraper.py >> /path/to/news-aggregator/scraper.log 2>&1
```

For Windows, use Task Scheduler with equivalent configuration. The `>> scraper.log 2>&1` redirect captures both output and errors so you can debug failed runs without being at the terminal.

If you're already building automation workflows, the same scraper can be integrated into tools like n8n — the pattern of fetch → parse → normalize → output maps naturally onto an HTTP Request node followed by data transformation steps.

## What to Do With the Data

Once you have a reliable CSV being populated on a schedule, the useful things you can do with it expand quickly.

- **Feed it into a database** — upsert by normalized URL, query by source or date range
- **Build a simple dashboard** — Looker Studio or Metabase on top of the CSV or database
- **Run keyword filtering** — flag articles matching specific terms and route them to Slack
- **Track story velocity** — measure how fast a topic spreads across sources over time
- **Pipe into an LLM** — summarize or categorize articles automatically

The scraper's job is just to get clean, consistent data into storage. What happens downstream is up to you.

This is the same underlying logic that applies to any structured web data collection — if you've ever thought about applying similar approaches to social data, the [build vs. buy tradeoffs for your own scraping infrastructure](https://scrapebadger.com/blog/build-vs-buy-should-you-build-your-own-twitter-scraper) are worth understanding before you scale up.

## FAQ

**What's the difference between scraping a static and a dynamic news site?**

Static sites return the full article content in the initial HTML response — `requests` + `BeautifulSoup` handles these directly. Dynamic sites render content via JavaScript after the page loads, so the initial HTML response is mostly empty. For those, you need a headless browser (Playwright or Selenium) that can execute JavaScript and wait for elements to appear. Check the page source manually first — it tells you immediately which type you're dealing with.

**Should I use RSS feeds instead of scraping HTML?**

Almost always yes, if a feed is available. RSS gives you structured, stable XML that almost never changes format. Install `feedparser` (`pip install feedparser`) and parse the feed directly — you skip HTML parsing entirely and get fields like `title`, `link`, `published`, and `summary` with no CSS selector guesswork. RSS feeds are also less likely to be subject to anti-scraping measures.

**How do I handle sites that block my scraper?**

Start with a realistic `User-Agent` header and delays between requests. Most static news sites don't aggressively block scrapers, especially at low request rates. If you're still getting blocked, rotate your User-Agent strings and add longer random delays. For sites using Cloudflare or similar protection, you'll need a proxy provider or a headless browser with stealth plugins. That said — if a site is that aggressive about blocking, it's worth checking whether they offer an RSS feed or API instead.

**How do I avoid duplicate articles across sources?**

Normalize URLs before deduplication — strip query parameters, fragments, and trailing slashes, then lowercase everything. Use the normalized URL as your unique key. For ongoing runs, persist seen URLs in a SQLite database between executions so you're not re-processing articles from previous runs.

**Is it legal to scrape news sites?**

It depends on jurisdiction, the site's terms of service, and what you do with the data. Most public news sites tolerate scraping for personal use and research. Commercial use, republishing content, or circumventing paywalls is a different matter. Always check `robots.txt` (`https://example.com/robots.txt`) and the site's ToS before scraping at scale. When in doubt, using the official RSS feed is usually unambiguous.

**What's the right frequency for running a news aggregator?**

It depends on how current you need the data. Hourly is sufficient for most monitoring and research use cases. Running more frequently than that is rarely necessary for news (news cycles aren't that fast) and increases the chance of getting rate-limited. If you need near-real-time updates, look for sites that offer RSS or WebSocket-based news feeds rather than polling HTML pages every few minutes.

**How do I track when a source's HTML structure changes and breaks my parser?**

The most practical approach is monitoring output volume per source. If a parser that normally returns 20 articles suddenly returns 0, something changed upstream. Log article counts per run and alert when a source drops to zero unexpectedly. You can extend this with a simple test that runs the parser on a saved HTML snapshot and checks that the output matches expected field counts — it won't catch every change, but it catches the most common case.