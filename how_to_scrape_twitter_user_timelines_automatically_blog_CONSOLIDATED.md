## SEO Metadata
Primary Keyword: twitter user timelines scraping
Meta Title: Twitter User Timelines Scraping: Full Guide
Meta Description: Master twitter user timelines scraping with this step-by-step guide. Build a Python pipeline that paginates, deduplicates, and exports tweet data automatically.


---

## LinkedIn Post
Most people scraping Twitter are doing keyword search. It works, but it answers only one question: what is the internet saying about a topic right now?

There is a different and often more valuable question: what has a specific account said over time?

Tracking competitor product accounts, following key researchers in your space, building training data for a domain-specific model, or adding context to lead research — all of these require timeline data, not keyword data. And timeline scraping is a different problem with its own failure modes.

The main one is pagination. A user with thousands of tweets does not hand them over in one response. You follow a cursor, page by page. Do it carelessly and you end up with gaps, duplicates, or silent early stops — a dataset that looks complete but is not.

The right approach involves handling pagination explicitly, normalizing raw tweet objects into a stable schema (fields appear and disappear depending on tweet type), deduplicating by tweet ID, and writing output atomically so a mid-run crash never leaves you with a corrupt file.

After the initial collection, incremental runs with SQLite make daily updates cheap. Cron handles the scheduling. The whole thing runs unattended.

I wrote a detailed guide covering the full pipeline — from a minimal working script to a scheduled, production-ready setup with common failure modes and how to handle them.

Worth reading if you are building any kind of structured data layer around Twitter activity.

scrapebadger.com

---

## Twitter Thread
Keyword search tells you what people are saying.
Timeline scraping tells you what a specific account has said for years.

Different tool. Different question. Most people only know one of them.

Read the full guide: scrapebadger.com

---

## Blog Cover Image
![Cover Image](/Users/milijonierius/Desktop/Domo workflow/how_to_scrape_twitter_user_timelines_automatically_blog_cover.png)

---

# How to Scrape Twitter User Timelines Automatically

Most tutorials about scraping Twitter focus on keyword search — collect tweets matching a query, export to CSV, done. That's useful, but it misses a whole category of data: the full posting history of specific accounts.

Scraping user timelines is a different problem. You're not hunting for mentions of a topic. You're tracking what a particular person or organization has said over time. That means dealing with pagination over potentially thousands of tweets, handling sparse periods and burst periods, and keeping your dataset current as new posts arrive.

This guide walks through how to do it correctly — starting from a working minimal script, building up to a scheduled pipeline that runs unattended.

## Why User Timeline Scraping Is Useful

Before the implementation details, it's worth being clear about what this is actually good for.

Tracking a competitor's product account lets you see what they announce, how often they post, which posts get traction, and what topics they've stopped talking about. That's a meaningful dataset for any startup that wants to understand where a market is moving.

Following key voices in a domain — analysts, researchers, practitioners — gives you a structured feed of signal without the noise of platform timelines. You can process it programmatically: filter by engagement, cluster by topic, or export to a doc for team review.

Building training data for a model that understands how a particular account or persona communicates requires a clean, timestamped history of their posts. You can't get that from keyword search.

And if you're running [lead generation through Twitter monitoring](https://scrapebadger.com/blog/how-startups-use-twitter-monitoring-for-lead-generation), timelines fill in context keyword search misses — you see the full picture of who someone is and what they care about before you decide whether to engage.

## The Core Challenge: Pagination

The thing that makes timeline scraping harder than it looks is pagination. A user with 5,000 tweets isn't going to give you all 5,000 in one response. You'll get a page of results and a cursor, and you need to follow that cursor page by page until you've collected what you need.

The problems that show up in practice:

- Gaps when cursor logic breaks or you hit a timeout mid-run
- Duplicates when you restart a job and overlap with the previous run's final page
- Inconsistent response shapes — some fields appear on some tweets and not others
- Silent failures where pagination stops early and the script reports success

None of these are fatal problems. But they require explicit handling. A script that just calls an endpoint and collects whatever it gets until it stops will produce a dataset you can't trust.

## What You'll Build

A Python script that:

- Fetches all tweets from a specified account up to a configurable limit
- Handles pagination internally
- Normalizes each tweet into a consistent schema
- Deduplicates by tweet ID
- Exports to CSV with atomic writes (no half-written files)
- Can be scheduled to run incrementally

## Step 1: Set Up the Environment

```bash
mkdir twitter-timeline-scraper
cd twitter-timeline-scraper
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

Install dependencies:

```bash
pip install scrapebadger
pip freeze > requirements.txt
```

Set your API key as an environment variable:

```bash
export SCRAPEBADGER_API_KEY="YOUR_API_KEY"
```

Create the output directory:

```bash
mkdir -p output
```

Project structure:

```
twitter-timeline-scraper/
  scrape_timeline.py
  output/
```

## Step 2: Fetch a Timeline (Minimal Working Version)

Start small. Prove the request works and inspect the response shape before building the full pipeline.

```python
import asyncio
import os
from scrapebadger import ScrapeBadger

async def fetch_timeline(username: str, limit: int = 20):
    api_key = os.getenv("SCRAPEBADGER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPEBADGER_API_KEY environment variable")

    async with ScrapeBadger(api_key=api_key) as client:
        stream = client.twitter.users.latest_tweets(username, max_items=limit)
        async for tweet in stream:
            print({
                "id": tweet.get("id"),
                "created_at": tweet.get("created_at"),
                "text": tweet.get("text", "")[:100],
                "likes": (tweet.get("public_metrics") or {}).get("like_count"),
            })

if __name__ == "__main__":
    asyncio.run(fetch_timeline("openai", limit=20))
```

Run it:

```bash
python scrape_timeline.py
```

What you're checking:

- Does `id` return a stable string you can use as a unique key?
- Are timestamps consistent and parseable?
- Is the `public_metrics` block present? What fields does it contain?
- Does the text ever look truncated?

This informs the normalization schema you'll build in the next step.

## Step 3: Normalize and Export to CSV

Raw tweet payloads are inconsistent. Fields appear and disappear depending on the tweet type, account settings, and API response shape. The normalization step converts that chaos into a predictable schema.

Define the schema first:

```python
CSV_COLUMNS = [
    "tweet_id",
    "created_at",
    "text",
    "like_count",
    "retweet_count",
    "reply_count",
    "quote_count",
]
```

Write the normalizer with safe defaults — never assume a field is present:

```python
def normalize(tweet: dict) -> dict:
    metrics = tweet.get("public_metrics") or {}
    return {
        "tweet_id":     str(tweet.get("id") or ""),
        "created_at":   str(tweet.get("created_at") or ""),
        "text":         str(tweet.get("text") or ""),
        "like_count":   int(metrics.get("like_count") or 0),
        "retweet_count": int(metrics.get("retweet_count") or 0),
        "reply_count":  int(metrics.get("reply_count") or 0),
        "quote_count":  int(metrics.get("quote_count") or 0),
    }
```

The `or ""` and `or 0` patterns matter. If a field is `None`, the cast to `str` or `int` would crash without the default. If it's missing entirely, `.get()` returns `None` and the default kicks in. Either way, the row is safe to write.

## Step 4: The Full Export Script

This version handles the complete pipeline: fetch → paginate → normalize → deduplicate → write atomically.

```python
import asyncio
import csv
import os
import time
from scrapebadger import ScrapeBadger

CSV_COLUMNS = [
    "tweet_id",
    "created_at",
    "text",
    "like_count",
    "retweet_count",
    "reply_count",
    "quote_count",
]

def normalize(tweet: dict) -> dict:
    metrics = tweet.get("public_metrics") or {}
    return {
        "tweet_id":      str(tweet.get("id") or ""),
        "created_at":    str(tweet.get("created_at") or ""),
        "text":          str(tweet.get("text") or ""),
        "like_count":    int(metrics.get("like_count") or 0),
        "retweet_count": int(metrics.get("retweet_count") or 0),
        "reply_count":   int(metrics.get("reply_count") or 0),
        "quote_count":   int(metrics.get("quote_count") or 0),
    }

async def export_timeline_to_csv(
    username: str,
    max_items: int,
    out_path: str,
    hard_timeout_seconds: int = 900,
):
    api_key = os.getenv("SCRAPEBADGER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SCRAPEBADGER_API_KEY environment variable")

    started = time.time()
    seen_ids: set[str] = set()

    async with ScrapeBadger(api_key=api_key) as client:
        stream = client.twitter.users.latest_tweets(username, max_items=max_items)

        tmp_path = out_path + ".tmp"
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()

            async for tweet in stream:
                if time.time() - started > hard_timeout_seconds:
                    print(f"Hard timeout reached after {hard_timeout_seconds}s")
                    break

                if not isinstance(tweet, dict):
                    tweet = getattr(tweet, "model_dump", lambda: dict(tweet))()

                row = normalize(tweet)

                if not row["tweet_id"]:
                    continue
                if row["tweet_id"] in seen_ids:
                    continue

                seen_ids.add(row["tweet_id"])
                writer.writerow(row)

    # Atomic replace — the file either exists and is complete, or doesn't exist
    os.replace(tmp_path, out_path)
    print(f"Exported {len(seen_ids)} tweets to {out_path}")

if __name__ == "__main__":
    asyncio.run(export_timeline_to_csv(
        username="openai",
        max_items=500,
        out_path="output/openai_timeline.csv",
        hard_timeout_seconds=900,
    ))
```

Run it:

```bash
python scrape_timeline.py
```

The `.tmp` → `os.replace()` pattern is worth noting. If the script crashes mid-run, you end up with a `.tmp` file, not a corrupt CSV. The final file is always either complete or absent — never half-written.

## Step 5: Incremental Runs (Collecting Only New Tweets)

A full re-fetch every time is wasteful and unnecessary once you have a baseline. The better pattern is to track the highest tweet ID you've seen and only fetch newer posts.

SQLite makes this easy — it's a single file, no server needed, and Python's standard library supports it directly.

```python
import sqlite3
from pathlib import Path

DB_FILE = Path("output/timeline.db")

def setup_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            tweet_id     TEXT PRIMARY KEY,
            username     TEXT NOT NULL,
            created_at   TEXT,
            text         TEXT,
            like_count   INTEGER DEFAULT 0,
            retweet_count INTEGER DEFAULT 0,
            reply_count  INTEGER DEFAULT 0,
            quote_count  INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()

def save_tweets(rows: list[dict], username: str) -> int:
    """Returns count of newly inserted rows."""
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    new_count = 0

    for row in rows:
        try:
            cur.execute("""
                INSERT INTO tweets
                    (tweet_id, username, created_at, text, like_count,
                     retweet_count, reply_count, quote_count)
                VALUES
                    (:tweet_id, :username, :created_at, :text, :like_count,
                     :retweet_count, :reply_count, :quote_count)
            """, {**row, "username": username})
            new_count += 1
        except sqlite3.IntegrityError:
            pass  # Already stored — expected on incremental runs

    con.commit()
    con.close()
    return new_count
```

On each run, `IntegrityError` is the normal success path for tweets you've already seen. The `tweet_id` primary key handles deduplication automatically.

## Step 6: Schedule the Job with Cron

Once the script works, scheduling is straightforward. On Linux/macOS, use cron:

```bash
crontab -e
```

Add a daily run at 8am for a single account:

```bash
# Fetch latest tweets from @openai daily at 8am
0 8 * * * /path/to/.venv/bin/python /path/to/scrape_timeline.py >> /path/to/timeline.log 2>&1
```

For multiple accounts, the cleanest pattern is to pass the username as a command-line argument:

```python
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scrape_timeline.py <username> [max_items]")
        sys.exit(1)
    username = sys.argv[1]
    max_items = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    asyncio.run(export_timeline_to_csv(username, max_items, f"output/{username}.csv"))
```

Then in cron:

```bash
0 8 * * * /path/to/.venv/bin/python /path/to/scrape_timeline.py openai 200 >> timeline.log 2>&1
0 8 * * * /path/to/.venv/bin/python /path/to/scrape_timeline.py anthropic 200 >> timeline.log 2>&1
0 8 * * * /path/to/.venv/bin/python /path/to/scrape_timeline.py googledeepmind 200 >> timeline.log 2>&1
```

Each account runs as a separate job. If one fails, the others aren't affected.

## Common Failure Modes

These are the problems that actually show up when you run this in production.

**Empty output — CSV has only headers**

Check first: is the username correct? Twitter handles are case-insensitive but typos matter. Second: does the account exist and is it public? Private accounts return no data. Third: is authentication working — run the minimal script to confirm you're getting a response at all.

**Duplicate tweet IDs across runs**

Cause: overlapping pagination on restart. Fix: the `seen_ids` set handles this within a single run. For across runs, the SQLite `PRIMARY KEY` constraint handles it. You should see `IntegrityError` on the second run for every tweet from the first — that's correct behavior.

**Truncated text**

Some tweet objects return shortened text. Check whether you need to request the full text explicitly via query parameters. If you're seeing `…` at the end of tweets, the endpoint may need a `tweet.fields=text` parameter or similar depending on the API version.

**Job completes too fast with suspiciously few results**

This usually means pagination stopped early — either the account genuinely has fewer tweets than you expected, or the stream ended unexpectedly. Add logging around the row count and compare against the account's visible tweet count as a sanity check.

## Choosing How Many Tweets to Collect

The right `max_items` value depends on what you're doing with the data.

| Use Case | Recommended max_items | Rationale |
|---|---|---|
| Initial baseline for a competitor account | 1,000–3,000 | Get enough history to identify posting patterns |
| Daily incremental update | 50–200 | Covers a day's activity with room for burst periods |
| Training data collection | 5,000+ | More data improves model quality |
| Trend analysis over a specific period | 500–1,000 | Cap by count, then filter by date range |
| Quick account audit | 100–200 | Fast enough to run interactively |

Start with a smaller number and confirm output quality before scaling up. A run that fetches 200 tweets and validates well is more useful than a run that fetches 5,000 and silently drops 40% of them.

## What Good Output Looks Like

Before you trust the data downstream, check:

- Headers are present and consistent on every run
- No duplicate `tweet_id` values (run `sort -u` on the column if checking manually)
- `created_at` timestamps are present and parseable — not empty strings or `None`
- `text` fields aren't uniformly truncated
- Engagement counts are numeric, not empty or `None`

If all of these pass, the dataset is safe to hand to analysis, a model, or a downstream automation.

## Production Considerations

A few things worth thinking about before you schedule this to run unattended for weeks.

**Alert on zero output.** If a job runs and returns zero tweets for an account that normally returns 100+, something is wrong. Instrument your jobs to log row counts per run and alert if a run produces nothing.

**Watch for schema changes.** If the `public_metrics` block changes shape or a field gets renamed, your normalizer will silently write zeros instead of real values. Periodic manual spot-checks catch this before it poisons weeks of data.

**Rate your requests sensibly.** If you're collecting timelines for 20 accounts per day, that's fine. If you're collecting 200 accounts every hour, think about whether that's actually necessary or whether you're generating noise you'll never look at.

**Store raw responses.** Keep the original tweet objects in a separate table alongside the normalized rows. When you need to extract a field you didn't think to include originally, you want to be able to reprocess history without re-fetching.

For a more in-depth look at real-time versus scheduled pipeline architectures, the guide on [building a real-time Twitter monitoring pipeline](https://scrapebadger.com/blog/how-to-build-a-real-time-twitter-monitoring-pipeline) covers the tradeoffs in detail.

## Practical Applications

**Tracking what a product account posts over time.** Build a weekly digest of what specific accounts in your market have shipped, announced, or complained about. This is far more useful than a one-time search.

**Building a training corpus.** If you're fine-tuning a model on a specific domain or communication style, a cleaned timeline export gives you a timestamped, structured dataset. The normalization step matters more here — garbage in, garbage out.

**Analyzing posting patterns.** Frequency histograms, engagement-per-post trends, and topic clustering all become possible once you have a consistent schema across multiple accounts over time. You can answer questions like "does posting frequency correlate with follower growth?" or "which content formats drive the most replies?"

**Content gap analysis.** Look at what topics a competitor stopped talking about. That's often more informative than what they're currently posting.

[ScrapeBadger](https://scrapebadger.com/docs/twitter) supports user timeline collection alongside keyword search, follower data, and engagement metrics — all through the same API and SDK, so you can mix and match without managing multiple integrations.

---

## FAQ

**What's the difference between user timeline scraping and keyword search?**

Keyword search finds all tweets matching a query, regardless of who posted them. Timeline scraping fetches all posts from a specific account. They answer different questions. Use keyword search when you want to know what the internet is saying about a topic. Use timeline scraping when you want to know what a specific account has said over time.

**How far back can I go with user timeline data?**

This depends on the API provider and the account. Some providers limit retrieval to the most recent 3,200 tweets (which matches the historical behavior of Twitter's own API). Accounts that post frequently may have a shorter effective history than accounts that post rarely. Set your `max_items` conservatively and check the earliest `created_at` timestamp in your output to see how far back you actually got.

**Can I scrape private Twitter accounts?**

No. Private accounts only show their posts to approved followers. Any scraping API that returns data from private accounts is doing something that will eventually break and may create legal exposure. Stick to public accounts.

**How do I avoid collecting retweets in my timeline data?**

Add a filter in your normalization step: check whether `tweet.get("text", "").startswith("RT @")` and skip those rows if you don't want retweets. A cleaner approach is to filter on a `referenced_tweets` field if the API returns it — that gives you explicit control over original posts versus retweets versus quote tweets.

**What's the right polling frequency for incremental timeline updates?**

It depends on how active the account is and how fresh you need the data. For most accounts, once per day is sufficient. For very active accounts during a product launch or live event, you might run every hour. Running more frequently than the account actually posts wastes credits and adds noise to your logs. A reasonable rule: if the last three runs all returned fewer than 5 new tweets, reduce the frequency.

**How do I handle accounts that change their username?**

Twitter account IDs are stable even when usernames change. If you're storing data long-term, consider storing the user ID alongside the username in your database. If a lookup by username fails, the account may have been suspended, deleted, or renamed — each case needs a different response.

**Is scraping user timelines legal?**

The short answer: it depends on your jurisdiction, how you use the data, and who you're targeting. Public account data is generally accessible, but platform terms of service vary and national data protection laws (GDPR, CCPA, etc.) impose constraints on storage and processing. Always review the relevant ToS and applicable law for your specific situation before collecting at scale or sharing the data externally.