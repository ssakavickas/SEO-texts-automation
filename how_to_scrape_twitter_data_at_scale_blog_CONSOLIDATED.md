## SEO Metadata
Primary Keyword: Scrape Twitter Data
Meta Title: How to Scrape Twitter Data at Scale
Meta Description: Learn how to scrape Twitter data reliably at scale. This guide covers pagination, normalization, deduplication, and building pipelines that run unattended.


---

## LinkedIn Post
Most Twitter scraping tutorials stop at 100 tweets. That number is useless for anything that matters.

The real challenge is not collecting tweets — it is building something that collects them reliably, every day, without you babysitting it. That gap between "it worked once" and "it runs unattended every hour" is where most pipelines quietly fall apart.

A few things that actually break at scale that never show up in tutorials:

Silent pagination gaps. The job finishes without an error, but you are missing three days of data and have no idea.

Schema drift. An API response quietly restructures a nested field. Your normalization writes empty strings for a week before anyone notices.

Duplicate accumulation. You run a job twice. Now your dataset has exact copies of 40,000 tweets and no clean way to fix it.

The solution to all three is not clever code. It is boring, deliberate architecture: a stable normalization layer that enforces safe defaults, SQLite-backed deduplication using PRIMARY KEY constraints, atomic file writes with os.replace(), and hard timeouts on every job.

The official X API is expensive at volume. DIY headless scraping breaks constantly. A scraping API handles the infrastructure layer so you can focus on the pipeline logic that actually matters.

If you are building anything beyond a one-time export, the engineering decisions you make in the first hour determine whether you have a pipeline or a maintenance burden.

Full guide with code at scrapebadger.com

---

## Twitter Thread
Scraping 100 tweets is easy.
Scraping 50,000 per week without losing data is a different problem entirely.

Pagination gaps, schema drift, silent duplicates — none of this shows up until scale does.

Read the full guide: scrapebadger.com

---

## Blog Cover Image
![Cover Image](/Users/milijonierius/Desktop/Domo workflow/how_to_scrape_twitter_data_at_scale_blog_cover.png)

---

# How to Scrape Twitter Data at Scale

Most Twitter scraping tutorials show you how to get 100 tweets. That's fine for a quick test. It's useless for anything real.

Scraping Twitter data at scale means handling pagination correctly, managing rate pressure, keeping output schemas stable across runs, and not losing data when something inevitably goes sideways. The gap between "it worked once" and "it works reliably every day" is where most pipelines die.

This guide covers what actually changes when you move from a proof-of-concept to a production scraping setup — the architecture decisions, the failure modes, and the practical steps to build something you can run unattended.

## What "Scale" Actually Means Here

Scale isn't just about volume. It's about reliability over time.

A scraper that collects <span style="color: #2D6A4F; font-weight: bold;">1,000 tweets</span> once is a script. A scraper that collects <span style="color: #2D6A4F; font-weight: bold;">50,000 tweets per week</span>, deduplicates across runs, maintains consistent output schemas, and recovers gracefully from failures — that's a pipeline.

In practice, scale introduces three problems that don't exist at small volume:

**Pagination reliability.** Twitter results paginate. At small volume, one page is often enough. At scale, you're chaining dozens of cursor-based requests, and any gap in pagination means silently missing data. Nothing crashes. The CSV just isn't complete.

**Data consistency.** Tweet objects aren't guaranteed uniform. Fields go missing. Nested structures change. At small volume, you notice immediately. At scale, one malformed record causes a schema mismatch that corrupts a week of exports before anyone spots it.

**Operational overhead.** A script you run manually is cheap to babysit. A pipeline running on a schedule across multiple keywords or accounts needs to handle failures, log what happened, and recover without your intervention. The engineering cost of maintaining a DIY scraper at scale is real and constant.

## The Architecture Decision That Matters Most

Before writing any code, decide on your data source. This choice shapes everything else.

| Option | Setup Time | Maintenance Burden | Cost at Volume | Reliability |
|---|---|---|---|---|
| Official X API (Basic) | Hours | Low | High ($100-200/month, strict limits) | High |
| DIY headless browser | Days–Weeks | Very High | Low (infra only) | Low |
| Scraping API (e.g., ScrapeBadger) | Hours | Low | Low–Medium | High |
| No-code platforms (n8n, Zapier) | Hours | Low | Medium–High at volume | Medium |

The official API is the obvious first thought, but the economics don't work for most teams. The Basic tier caps at roughly <span style="color: #2D6A4F; font-weight: bold;">300 requests per 15-minute window</span>, and the rate limits compound fast when you're running multi-keyword jobs. Full archive access starts at <span style="color: #2D6A4F; font-weight: bold;">$5,000/month</span>. That's a real bill for a research or monitoring use case.

DIY scraping with a headless browser is cheap in infrastructure but expensive in engineering time. Twitter's anti-bot detection is aggressive. Scrapers break on page structure changes, and those changes happen without notice. You'll spend more time patching the scraper than using the data.

Scraping APIs sit in between. They handle proxy rotation, request pacing, retries, and response normalization internally. You call an endpoint, get structured JSON, and focus on the pipeline logic that matters. When Twitter changes something under the hood, the provider handles it.

For anything that runs on a schedule across serious data volumes, the scraping API approach is the lowest total cost of ownership.

## What You're Building

The architecture for a production-scale Twitter scraper is the same regardless of data volume. It has four layers:

1. **Collection** — Call an API, handle pagination, stream results
2. **Normalization** — Flatten raw tweet objects into a stable, predictable schema
3. **Deduplication** — Track tweet IDs so reruns don't create duplicates
4. **Export** — Write clean output to a file, database, or downstream system

Each layer has a single responsibility. That separation is what makes the pipeline debuggable when something breaks.

## Step 1: Set Up Your Environment

Keep this project isolated. Dependencies drift, and "works on my machine" compounds over time.

```bash
mkdir twitter-scale-scraper
cd twitter-scale-scraper
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install scrapebadger
pip freeze > requirements.txt
```

Set your API key as an environment variable. Never hardcode credentials.

```bash
export SCRAPEBADGER_API_KEY="your_api_key_here"
```

Quick check:

```bash
python -c "import os; print('ok' if os.getenv('SCRAPEBADGER_API_KEY') else 'missing')"
```

Project structure:

```
twitter-scale-scraper/
  scraper.py
  output/
  checkpoints/
```

```bash
mkdir -p output checkpoints
```

## Step 2: Build the Collection Layer

Start with a minimal version that proves the data source works. Don't optimize before you've confirmed the basics.

```python
import asyncio
import os
from scrapebadger import ScrapeBadger

async def fetch_tweets(query: str, limit: int = 50):
    api_key = os.getenv("SCRAPEBADGER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPEBADGER_API_KEY")

    async with ScrapeBadger(api_key=api_key) as client:
        stream = client.twitter.tweets.search_all(query, max_items=limit)
        async for tweet in stream:
            print({
                "id": tweet.get("id"),
                "text": tweet.get("text", "")[:80],
                "created_at": tweet.get("created_at"),
            })

if __name__ == "__main__":
    asyncio.run(fetch_tweets("python data engineering", limit=20))
```

Run it. Confirm you're getting tweet IDs, timestamps, and text. If any of those are missing or inconsistent, investigate before building further — your normalization layer depends on understanding the actual response shape.

## Step 3: Normalization (The Schema Is a Contract)

Raw tweet payloads are fine for debugging. They're not acceptable as pipeline output. Fields go missing, nesting changes, and if your downstream code assumes a fixed structure, you get silent failures or crashes.

Normalization solves this by enforcing a stable schema with safe defaults for every field.

```python
def normalize(tweet: dict) -> dict:
    metrics = tweet.get("public_metrics") or {}
    user = tweet.get("user") or {}

    return {
        "tweet_id":       str(tweet.get("id") or ""),
        "created_at":     str(tweet.get("created_at") or ""),
        "username":       str(user.get("username") or ""),
        "display_name":   str(user.get("name") or ""),
        "text":           str(tweet.get("text") or ""),
        "like_count":     int(metrics.get("like_count") or 0),
        "retweet_count":  int(metrics.get("retweet_count") or 0),
        "reply_count":    int(metrics.get("reply_count") or 0),
        "quote_count":    int(metrics.get("quote_count") or 0),
        "lang":           str(tweet.get("lang") or ""),
        "is_retweet":     bool(tweet.get("referenced_tweets") and
                              any(r.get("type") == "retweeted"
                                  for r in tweet.get("referenced_tweets", []))),
    }
```

A few things worth noting here:

- Every field has a fallback. `or ""` or `or 0` means a missing field produces a safe default, not a `KeyError`.
- `tweet_id` is always a string. Tweet IDs overflow JavaScript's integer precision when cast to float — string is the right type.
- `is_retweet` is extracted at normalization time. At scale, you'll often want to filter retweets downstream. Having it as a pre-computed boolean is cheaper than re-parsing the referenced_tweets array repeatedly.

Treat the output schema as a contract. Every run should produce the same columns in the same order. That's what makes downstream analysis predictable.

## Step 4: Deduplication That Actually Works

At scale, you'll hit the same tweets from multiple sources: overlapping pagination windows, re-running a job, collecting the same keyword from two different queries. Without deduplication, your dataset accumulates garbage at the same rate it accumulates signal.

For single-run deduplication, an in-memory set is fine:

```python
seen_ids: set[str] = set()

# Inside your processing loop:
row = normalize(tweet)
if not row["tweet_id"] or row["tweet_id"] in seen_ids:
    continue
seen_ids.add(row["tweet_id"])
```

For pipelines that run on a schedule and need cross-run deduplication, persist tweet IDs to SQLite:

```python
import sqlite3

def setup_checkpoint_db(db_path: str):
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS seen (tweet_id TEXT PRIMARY KEY)")
    con.commit()
    con.close()

def is_new(tweet_id: str, db_path: str) -> bool:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO seen VALUES (?)", (tweet_id,))
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()
```

The `PRIMARY KEY` constraint does the work. If a tweet ID already exists, the insert fails and you skip it. Simple, reliable, and it survives restarts.

## Step 5: The Full Pipeline

This version combines everything: collection, normalization, deduplication, hard timeouts, and atomic CSV export.

```python
import asyncio
import csv
import os
import time
from scrapebadger import ScrapeBadger

CSV_COLUMNS = [
    "tweet_id", "created_at", "username", "display_name",
    "text", "like_count", "retweet_count", "reply_count",
    "quote_count", "lang", "is_retweet",
]

def normalize(tweet: dict) -> dict:
    metrics = tweet.get("public_metrics") or {}
    user = tweet.get("user") or {}
    return {
        "tweet_id":       str(tweet.get("id") or ""),
        "created_at":     str(tweet.get("created_at") or ""),
        "username":       str(user.get("username") or ""),
        "display_name":   str(user.get("name") or ""),
        "text":           str(tweet.get("text") or ""),
        "like_count":     int(metrics.get("like_count") or 0),
        "retweet_count":  int(metrics.get("retweet_count") or 0),
        "reply_count":    int(metrics.get("reply_count") or 0),
        "quote_count":    int(metrics.get("quote_count") or 0),
        "lang":           str(tweet.get("lang") or ""),
        "is_retweet":     bool(
            tweet.get("referenced_tweets") and
            any(r.get("type") == "retweeted"
                for r in tweet.get("referenced_tweets", []))
        ),
    }

async def run_scrape(
    query: str,
    max_items: int,
    out_path: str,
    hard_timeout_seconds: int = 900,
):
    api_key = os.getenv("SCRAPEBADGER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPEBADGER_API_KEY")

    started = time.time()
    seen_ids: set[str] = set()
    exported = 0
    skipped = 0

    async with ScrapeBadger(api_key=api_key) as client:
        stream = client.twitter.tweets.search_all(query, max_items=max_items)

        tmp_path = out_path + ".tmp"
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()

            async for tweet in stream:
                if time.time() - started > hard_timeout_seconds:
                    print(f"[timeout] Hard limit reached after {hard_timeout_seconds}s")
                    break

                if not isinstance(tweet, dict):
                    tweet = getattr(tweet, "model_dump", lambda: dict(tweet))()

                row = normalize(tweet)

                if not row["tweet_id"]:
                    skipped += 1
                    continue
                if row["tweet_id"] in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(row["tweet_id"])
                writer.writerow(row)
                exported += 1

        # Atomic write — no partial files
        os.replace(tmp_path, out_path)

    elapsed = round(time.time() - started, 1)
    print(f"Done. Exported: {exported} | Skipped: {skipped} | Time: {elapsed}s")

if __name__ == "__main__":
    asyncio.run(run_scrape(
        query="machine learning -is:retweet lang:en",
        max_items=5000,
        out_path="output/tweets.csv",
        hard_timeout_seconds=900,
    ))
```

A few things to call out:

- `hard_timeout_seconds` bounds the job wall-clock time. Without it, a slow network or unexpectedly deep pagination can run forever.
- `os.replace(tmp_path, out_path)` is atomic on POSIX systems. If the script dies mid-write, you get the previous complete file, not a corrupt partial one.
- The print at the end gives you a per-run summary: exported count, skipped count, runtime. That's the minimum observability for an unattended job.

## Scaling to Multiple Keywords

The single-query version above is fine for one keyword. In practice, you're usually monitoring several: your product name, a competitor, a market category, a campaign hashtag.

The simplest approach is to parameterize and loop:

```python
KEYWORDS = [
    "your-product-name -is:retweet lang:en",
    "competitor-product -is:retweet lang:en",
    "industry keyword 2025 -is:retweet",
]

async def run_all():
    for query in KEYWORDS:
        # Sanitize query string for filename
        safe_name = query[:40].replace(" ", "_").replace('"', "")
        out_path = f"output/{safe_name}.csv"
        print(f"\n--- Scraping: {query} ---")
        await run_scrape(
            query=query,
            max_items=2000,
            out_path=out_path,
            hard_timeout_seconds=600,
        )

if __name__ == "__main__":
    asyncio.run(run_all())
```

If you're collecting more than <span style="color: #2D6A4F; font-weight: bold;">50,000 tweets per day</span> across multiple queries, consider running keywords in parallel using `asyncio.gather()`. Just be mindful of any per-account credit limits and add a brief delay between jobs if you hit throughput issues.

## Query Syntax That Actually Filters

At scale, noise is the main enemy. The more tweets you collect, the more time you spend filtering irrelevant content downstream. Better to filter at the query level.

| Operator | Example | What It Does |
|---|---|---|
| `-is:retweet` | `python -is:retweet` | Exclude retweets |
| `lang:en` | `python lang:en` | English only |
| `min_faves:10` | `python min_faves:10` | Minimum engagement floor |
| `-filter:links` | `brand -filter:links` | Exclude link-heavy spam |
| `from:handle` | `from:elonmusk` | Specific account |
| `"exact phrase"` | `"machine learning"` | Exact match |
| `-giveaway -contest` | `brand -giveaway -contest` | Exclude promo noise |

Combining operators:

```
"your product" -is:retweet lang:en min_faves:5 -giveaway -contest
```

This one query eliminates retweets, non-English content, spam, and low-engagement posts. The result dataset is smaller, but the signal density is much higher.

## Failure Modes at Scale

The failures that don't show up at small volume:

**Silent pagination gaps.** The stream completes without error but skips pages due to cursor issues or upstream timeouts. The fix: log tweet counts per job and alert when output drops significantly below the expected range.

**Schema drift.** An API response starts returning a field in a new nested structure. Your normalization silently writes empty strings instead of values. The fix: defensive parsing with safe defaults, and periodic audits of output data quality.

**Duplicate accumulation.** You run the same job twice (manually or due to a retry). Without cross-run deduplication, your dataset grows with exact duplicates. The fix: persist tweet IDs in SQLite and use `PRIMARY KEY` constraint inserts.

**Runaway jobs.** A pagination loop hits an unexpected state and keeps running. The fix: always set both `max_items` and a hard wall-clock timeout.

**Half-written output files.** The script dies mid-write, leaving a corrupted CSV. The fix: always write to a `.tmp` file and use `os.replace()` to swap atomically.

## Production Hardening Checklist

Before scheduling anything to run unattended:

- Hard timeout set on every job
- `max_items` bounded — never open-ended
- Deduplication enabled (in-memory for single run, SQLite for scheduled)
- Atomic file writes (`.tmp` + `os.replace`)
- Per-run logging: tweet count, skip count, runtime, any errors
- Alert on near-zero output for queries that normally return results
- Separate output files per keyword/query
- Dependencies pinned in `requirements.txt`

This isn't over-engineering. These are the basics that separate a script you run once from a pipeline you trust.

## Scheduling the Pipeline

Once the script runs reliably manually, automate it with cron:

```bash
crontab -e
```

```
# Run every hour across all keywords
0 * * * * /path/to/.venv/bin/python /path/to/scraper.py >> /path/to/scraper.log 2>&1
```

Use absolute paths. Cron runs in a minimal environment and doesn't inherit your shell's `PATH`. The `>> scraper.log 2>&1` redirects both stdout and stderr to a log file you can inspect after the fact.

If you'd rather skip the scheduling infrastructure entirely, [building this as an n8n workflow](https://scrapebadger.com/blog/how-to-scrape-twitterx-tweets-with-n8n-using-scrapebadger-and-send-the-data-anywhere) is a clean alternative — you get visual scheduling, retry logic, and easy routing to downstream destinations without writing cron jobs.

## When to Move to a Database

CSV is fine up to a few hundred thousand rows. Beyond that, you want a database.

The migration is straightforward: replace the CSV writer with SQLite upserts (or PostgreSQL if you need concurrent access), using `tweet_id` as the primary key:

```python
import sqlite3

def upsert_tweet(row: dict, db_path: str):
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT OR IGNORE INTO tweets
            (tweet_id, created_at, username, text, like_count, retweet_count)
        VALUES
            (:tweet_id, :created_at, :username, :text, :like_count, :retweet_count)
    """, row)
    con.commit()
    con.close()
```

`INSERT OR IGNORE` handles deduplication at the database level — no need for an in-memory `seen_ids` set. Once you're past a few million rows, add an index on `created_at` for time-range queries and on `username` if you filter by account frequently.

For more on working with Twitter data in structured storage, the [Twitter dataset for machine learning guide](https://scrapebadger.com/blog/how-to-build-a-twitter-dataset-for-machine-learning) covers schema design for downstream modeling use cases.

## FAQ

**How many tweets can I realistically collect per day?**

It depends on your query breadth and rate limits. A focused keyword query with `ScrapeBadger` running hourly, collecting <span style="color: #2D6A4F; font-weight: bold;">1,000 tweets</span> per run, gives you roughly <span style="color: #2D6A4F; font-weight: bold;">24,000 tweets per day</span> per keyword. Broad queries or parallel keyword collection can push well past <span style="color: #2D6A4F; font-weight: bold;">100,000 per day</span>. The practical ceiling is determined by your API plan's credit allocation and the actual tweet volume for your queries.

**How do I avoid collecting duplicate tweets across multiple runs?**

Use `tweet_id` as your deduplication key. For scheduled jobs, persist seen IDs in a SQLite database with a `PRIMARY KEY` constraint. Any attempt to insert a duplicate raises an `IntegrityError` that you catch and ignore. This works across restarts and is cheap at scale.

**Is scraping Twitter/X data legal?**

This depends on jurisdiction, how the data is used, and the platform's current terms. Public tweet data is generally treated differently from private user data, but you should review the relevant ToS and applicable laws before building a production pipeline. When in doubt, using structured API access reduces legal ambiguity compared to direct web scraping.

**What's the right `max_items` for a scheduled scraping job?**

Cap it conservatively and run more frequently rather than setting a high limit and running less often. For most monitoring use cases, <span style="color: #2D6A4F; font-weight: bold;">500–2,000 tweets</span> per run every 15–60 minutes is more reliable than one massive job per day. Smaller bounded runs are easier to debug, easier to retry, and less likely to hit timeout issues.

**When should I filter retweets?**

Almost always. Retweets amplify existing content — they rarely contain new signal. For brand monitoring, sentiment analysis, or dataset building, filtering with `-is:retweet` cuts volume significantly and improves data quality. The main exception is if you're specifically studying how content spreads, in which case retweet data is what you want.

**How do I handle schema changes in the API response?**

Always use defensive parsing: `tweet.get("field") or default_value`. Never assume a field exists. Write your normalization function to handle missing fields with safe defaults, and add a validation step that checks required fields before writing rows. If `tweet_id` or `text` is missing, skip the row rather than writing a corrupted record.

**What's the difference between polling and real-time streaming?**

Polling runs on a schedule — you ask for recent tweets at regular intervals. This is fine for most monitoring and dataset-building use cases. Real-time streaming pushes tweets to you the moment they match a filter rule, with latency measured in seconds rather than minutes. If you need fast reaction times (crisis monitoring, live event tracking), streaming is the right primitive. For everything else, polling is simpler to operate and easier to debug.