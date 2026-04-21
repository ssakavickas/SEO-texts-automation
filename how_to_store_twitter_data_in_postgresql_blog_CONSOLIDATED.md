## SEO Metadata
Primary Keyword: twitter data
Meta Title: How to Store Twitter Data in PostgreSQL
Meta Description: Learn how to store Twitter data in PostgreSQL with schema design, deduplication, and ingestion pipelines. Build a scalable setup that handles millions of tweets.


---

## LinkedIn Post
Most people hit the same wall at the same moment: a CSV file with 50,000 tweets, a question that needs a real answer, and no clean way to get there.

That is when you realize a spreadsheet was never a data store. It was just a delay.

PostgreSQL is the right move for serious Twitter data work, and the reasons are more specific than "it scales." Tweet IDs are 64-bit integers that sort chronologically by design. Storing them as strings quietly breaks that. The JSONB column type means you can keep the raw payload intact, so when Twitter's schema changes six months from now, your historical data is still reprocessable. And ON CONFLICT DO NOTHING makes deduplication a database concern instead of something your application has to babysit.

The schema decisions matter more than people expect. A two-table setup with tweets and users, a keyword column to track which search produced each result, and a raw JSONB fallback for fields that do not fit neatly into columns, covers most real-world monitoring needs without overengineering.

The part that trips people up most often is insert order. Users before tweets, every time, or the foreign key constraint will take down the whole batch. It is a simple rule that causes a lot of confusion until you have seen it fail once.

If you are collecting Twitter data for anything beyond a one-time export, the full schema, ingestion pipeline, and query examples are worth reading through carefully.

scrapebadger.com

---

## Twitter Thread
CSV files break the moment you need real answers from tweet data.

PostgreSQL handles it properly: BIGINT IDs, JSONB for raw payloads, ON CONFLICT for clean dedup.

Read the full guide: scrapebadger.com

---

## Blog Cover Image
![Cover Image](/Users/milijonierius/Desktop/Domo workflow/how_to_store_twitter_data_in_postgresql_blog_cover.png)

---

# How to Store Twitter Data in PostgreSQL

CSV files are fine until they aren't. The moment you need to query across 50,000 tweets, join engagement metrics to user data, or run any kind of trend analysis that goes beyond "open in Excel," you'll want a real database. PostgreSQL is the right call: it handles structured tweet data well, supports JSON for the fields that don't fit neatly into columns, and scales from a laptop experiment to a production system without changing your mental model.

This guide covers the full pipeline — schema design, ingestion, deduplication, and the practical decisions that determine whether your setup holds up over weeks, not just one afternoon.

## Why PostgreSQL Over the Alternatives

SQLite works fine for single-process monitoring bots where one script reads and writes sequentially. Once you have multiple jobs writing data concurrently, or you want to query while ingestion is running, SQLite becomes a constraint. MongoDB is a reasonable choice if tweet data stays unstructured forever, but most teams eventually want to aggregate, join, and filter in ways that SQL handles more naturally than document queries.

PostgreSQL gives you:

- Native `BIGINT` for tweet IDs (which are 64-bit integers — don't store them as strings unless you enjoy subtle ordering bugs)
- `JSONB` for semi-structured fields like `entities`, `public_metrics`, and `context_annotations` that can change shape between tweets
- `ON CONFLICT DO NOTHING` for idempotent upserts, which is the clean way to handle deduplication at the database level
- Extensions like `pg_trgm` for fuzzy text search and `TimescaleDB` for time-series queries on tweet volumes

The ecosystem around Postgres is also mature. `psycopg2` and `asyncpg` are stable, well-documented Python drivers. Every major BI tool connects to it. Free tiers on Neon, Supabase, and Railway are sufficient for prototyping.

## Schema Design

The biggest decision is how much to normalize. You have two ends of the spectrum: fully flatten everything into one wide table, or split tweets and users into separate tables with a foreign key relationship.

In practice, a two-table schema with a JSONB escape hatch for edge cases is the right starting point.

```sql
-- Users table
CREATE TABLE IF NOT EXISTS twitter_users (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT NOT NULL,
    display_name TEXT,
    description TEXT,
    follower_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    verified    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tweets table
CREATE TABLE IF NOT EXISTS tweets (
    tweet_id        BIGINT PRIMARY KEY,
    user_id         BIGINT REFERENCES twitter_users(user_id),
    text            TEXT,
    created_at      TIMESTAMP WITH TIME ZONE,
    like_count      INTEGER DEFAULT 0,
    retweet_count   INTEGER DEFAULT 0,
    reply_count     INTEGER DEFAULT 0,
    quote_count     INTEGER DEFAULT 0,
    lang            TEXT,
    is_retweet      BOOLEAN DEFAULT FALSE,
    keyword         TEXT,           -- which search query captured this tweet
    entities        JSONB,          -- hashtags, mentions, URLs
    raw             JSONB,          -- full original payload for reprocessing
    inserted_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_keyword ON tweets (keyword);
CREATE INDEX IF NOT EXISTS idx_tweets_user_id ON tweets (user_id);
CREATE INDEX IF NOT EXISTS idx_tweets_entities ON tweets USING GIN (entities);
```

A few decisions worth calling out:

**`tweet_id` as `BIGINT`, not `VARCHAR`.** Twitter IDs are 64-bit integers. Storing them as strings wastes space, breaks chronological sorting by ID (Snowflake IDs are monotonically increasing), and occasionally causes comparison bugs when mixing types. Use `BIGINT`.

**Keep the `raw` JSONB column.** Tweet JSON shapes change over time. Fields get added, nested structures shift, new metric types appear. Storing the original payload means you can reprocess historical data when your schema evolves, without re-collecting anything.

**Track `keyword`.** If you're running searches for multiple topics, this column lets you filter and analyze per-campaign without separate tables.

## The Ingestion Pipeline

Here's a complete script that fetches tweets by keyword using ScrapeBadger, normalizes them, and upserts into PostgreSQL. It handles deduplication at the database level using `ON CONFLICT DO NOTHING` — simpler and more reliable than in-memory ID tracking when you're running scheduled jobs.

```python
import asyncio
import os
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from scrapebadger import ScrapeBadger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── Database connection ─────────────────────────────────────────────────────

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432)),
        dbname=os.getenv("PG_DBNAME", "twitter_db"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
    )

# ── Normalization ───────────────────────────────────────────────────────────

def normalize_user(user: dict) -> dict | None:
    if not user:
        return None
    return {
        "user_id":        int(user.get("id") or 0) or None,
        "username":       str(user.get("username") or ""),
        "display_name":   str(user.get("name") or ""),
        "description":    str(user.get("description") or ""),
        "follower_count": int((user.get("public_metrics") or {}).get("followers_count") or 0),
        "following_count": int((user.get("public_metrics") or {}).get("following_count") or 0),
        "verified":       bool(user.get("verified") or False),
    }

def normalize_tweet(tweet: dict, keyword: str) -> dict | None:
    tweet_id_raw = tweet.get("id")
    if not tweet_id_raw:
        return None

    metrics = tweet.get("public_metrics") or {}
    return {
        "tweet_id":     int(tweet_id_raw),
        "user_id":      int((tweet.get("user") or {}).get("id") or 0) or None,
        "text":         str(tweet.get("text") or ""),
        "created_at":   tweet.get("created_at"),
        "like_count":   int(metrics.get("like_count") or 0),
        "retweet_count": int(metrics.get("retweet_count") or 0),
        "reply_count":  int(metrics.get("reply_count") or 0),
        "quote_count":  int(metrics.get("quote_count") or 0),
        "lang":         tweet.get("lang"),
        "is_retweet":   bool(tweet.get("referenced_tweets")),
        "keyword":      keyword,
        "entities":     psycopg2.extras.Json(tweet.get("entities") or {}),
        "raw":          psycopg2.extras.Json(tweet),
    }

# ── Database writes ─────────────────────────────────────────────────────────

def upsert_user(cur, user_data: dict):
    cur.execute("""
        INSERT INTO twitter_users
            (user_id, username, display_name, description, follower_count, following_count, verified)
        VALUES
            (%(user_id)s, %(username)s, %(display_name)s, %(description)s,
             %(follower_count)s, %(following_count)s, %(verified)s)
        ON CONFLICT (user_id) DO UPDATE SET
            username       = EXCLUDED.username,
            follower_count = EXCLUDED.follower_count,
            updated_at     = NOW()
    """, user_data)

def insert_tweet(cur, tweet_data: dict) -> bool:
    """Returns True if the tweet was new, False if it already existed."""
    cur.execute("""
        INSERT INTO tweets
            (tweet_id, user_id, text, created_at, like_count, retweet_count,
             reply_count, quote_count, lang, is_retweet, keyword, entities, raw)
        VALUES
            (%(tweet_id)s, %(user_id)s, %(text)s, %(created_at)s, %(like_count)s,
             %(retweet_count)s, %(reply_count)s, %(quote_count)s, %(lang)s,
             %(is_retweet)s, %(keyword)s, %(entities)s, %(raw)s)
        ON CONFLICT (tweet_id) DO NOTHING
    """, tweet_data)
    return cur.rowcount > 0

# ── Main pipeline ───────────────────────────────────────────────────────────

async def collect_to_postgres(keyword: str, max_items: int = 500):
    api_key = os.getenv("SCRAPEBADGER_API_KEY")
    if not api_key:
        raise RuntimeError("SCRAPEBADGER_API_KEY is not set")

    conn = get_db_connection()
    cur = conn.cursor()

    new_count = 0
    skip_count = 0

    try:
        async with ScrapeBadger(api_key=api_key) as client:
            stream = client.twitter.tweets.search_all(keyword, max_items=max_items)

            async for raw_tweet in stream:
                if not isinstance(raw_tweet, dict):
                    raw_tweet = getattr(raw_tweet, "model_dump", lambda: dict(raw_tweet))()

                # Upsert the user first (satisfies foreign key constraint)
                user_data = normalize_user(raw_tweet.get("user") or {})
                if user_data and user_data["user_id"]:
                    upsert_user(cur, user_data)

                # Insert the tweet
                tweet_data = normalize_tweet(raw_tweet, keyword)
                if not tweet_data:
                    continue

                if insert_tweet(cur, tweet_data):
                    new_count += 1
                else:
                    skip_count += 1

                # Commit in batches of 100 to avoid holding large transactions
                if (new_count + skip_count) % 100 == 0:
                    conn.commit()
                    logging.info(f"Progress: {new_count} new, {skip_count} skipped")

        conn.commit()
        logging.info(f"Done — {new_count} new tweets, {skip_count} already existed")

    except Exception as e:
        conn.rollback()
        logging.error(f"Pipeline error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    asyncio.run(collect_to_postgres("python scraping", max_items=500))
```

A few things worth noting about the implementation:

**Batch commits every 100 rows.** Holding one massive transaction for 10,000 tweet inserts increases memory pressure and means a failure late in the job loses everything. Committing in batches is a reasonable middle ground between per-row commits (slow) and one giant commit (fragile).

**User upsert before tweet insert.** The `twitter_users` table has a primary key that `tweets.user_id` references. Insert order matters. If you get the order wrong and hit a foreign key violation, the whole batch rolls back.

**`ON CONFLICT DO UPDATE` for users, `ON CONFLICT DO NOTHING` for tweets.** User metadata changes — follower counts, display names. You want to keep that fresh. Tweet content doesn't change meaningfully after posting, so silently ignoring duplicates is correct.

## Querying Your Data

Once data is flowing, the queries you'll actually run:

```sql
-- Tweets per day for a keyword
SELECT
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*) AS tweet_count,
    SUM(like_count) AS total_likes
FROM tweets
WHERE keyword = 'python scraping'
GROUP BY 1
ORDER BY 1 DESC;

-- Top tweets by engagement
SELECT tweet_id, username, text, like_count + retweet_count AS engagement
FROM tweets
JOIN twitter_users USING (user_id)
WHERE keyword = 'python scraping'
ORDER BY engagement DESC
LIMIT 20;

-- Hashtag frequency from JSONB entities
SELECT
    tag->>'tag' AS hashtag,
    COUNT(*) AS occurrences
FROM tweets,
     JSONB_ARRAY_ELEMENTS(entities->'hashtags') AS tag
WHERE keyword = 'python scraping'
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;
```

The `JSONB_ARRAY_ELEMENTS` query is why storing `entities` as JSONB is worth it. You don't need a separate `hashtags` table for occasional queries like this, but you still get the flexibility to go there later.

## Storage and Performance Considerations

| Factor | Recommendation | Why |
|---|---|---|
| Tweet ID type | `BIGINT` | 64-bit integers, Snowflake IDs sort chronologically |
| Duplicate handling | `ON CONFLICT DO NOTHING` | Cleaner than in-memory dedup for multi-process jobs |
| Raw payload | Store as `JSONB` | Allows reprocessing without re-collection |
| Index on `created_at` | Yes, descending | Almost every useful query filters by time range |
| Index on `keyword` | Yes | Required if you monitor multiple topics |
| GIN index on `entities` | For active query workloads | Expensive to build, powerful for hashtag/mention queries |
| Commit frequency | Every 100–200 rows | Balances transaction overhead vs. failure recovery |
| Partitioning | Consider after ~5M rows | Partition by month on `created_at` |

If you're collecting tweets at high volume over months, look at [TimescaleDB](https://www.timescale.com/) as a Postgres extension. It adds time-series hypertables, automatic partitioning by time interval, and compression that typically cuts storage by 80–90% on time-ordered data. The query interface stays standard SQL.

## Common Failure Modes

**Foreign key violations.** If a tweet's user record doesn't exist yet, the insert fails. Always upsert users before inserting their tweets, or temporarily defer foreign key checks if you're loading in bulk.

**Timezone drift.** Tweet `created_at` timestamps from the API come in various formats. Normalize everything to `TIMESTAMP WITH TIME ZONE` at ingestion time. Mixing timezone-aware and naive timestamps in a single column creates query results that look correct but aren't.

**Storing tweet IDs as integers after JSON parsing.** Python's `json.loads()` handles 64-bit integers fine. Some older JSON parsers silently truncate them. If tweet IDs look subtly wrong (last few digits are zeroed out), that's your problem.

**Schema evolution.** Tweet JSON grows over time. The `raw JSONB` column is your insurance policy — when a new field appears that you care about, you can backfill it from stored payloads rather than losing historical data.

For a simpler starting point before you commit to PostgreSQL, see [how to export tweets to CSV using Python](https://scrapebadger.com/blog/how-to-export-tweets-to-csv-using-python). Once you're ready to build ongoing monitoring on top of the database, [how to build a Twitter alert system for your startup](https://scrapebadger.com/blog/how-to-build-a-twitter-alert-system-for-your-startup) covers routing new tweets to Slack as they land.

## Environment Setup

```bash
# Install dependencies
pip install scrapebadger psycopg2-binary

# Set credentials
export SCRAPEBADGER_API_KEY="your_api_key"
export PG_HOST="localhost"
export PG_DBNAME="twitter_db"
export PG_USER="postgres"
export PG_PASSWORD="your_password"

# Create the database
createdb twitter_db

# Run the schema (save the CREATE TABLE statements above to schema.sql)
psql -d twitter_db -f schema.sql
```

For local development, a Docker Postgres instance is the fastest path:

```bash
docker run -d \
  --name twitter-pg \
  -e POSTGRES_DB=twitter_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=localpass \
  -p 5432:5432 \
  postgres:15-alpine
```

## FAQ

**What data type should I use for tweet IDs in PostgreSQL?**

Use `BIGINT`. Twitter IDs are 64-bit integers — the Snowflake format embeds a timestamp in the high bits, which means they sort chronologically. Storing them as `VARCHAR` wastes space and breaks that ordering property. If you see recommendations to use `VARCHAR` for safety, they're usually working around a JSON parsing library that couldn't handle 64-bit integers cleanly, which isn't a problem in Python.

**How do I handle duplicate tweets when running jobs on a schedule?**

The cleanest approach is `ON CONFLICT (tweet_id) DO NOTHING` in your INSERT statement. This makes every insert idempotent — you can re-run the same job twice and the database ends up in the same state. This is more reliable than in-memory deduplication sets, especially when you're running multiple concurrent jobs or recovering from a failed run.

**Should I store the full raw tweet JSON or just the fields I need?**

Store both. Extract the fields you know you need into proper columns (they'll be fast to query and easy to index), and keep the full raw payload in a `JSONB` column. Tweet JSON schemas evolve — new fields appear, nested structures change. The raw column means you can backfill new columns from historical data without re-collecting anything. Storage is cheap. Re-collection is not.

**How do I query hashtags efficiently from the JSONB entities field?**

Use `JSONB_ARRAY_ELEMENTS` to unnest the hashtag array, and create a GIN index on the `entities` column: `CREATE INDEX ON tweets USING GIN (entities)`. GIN indexes accelerate containment queries (`entities @> '{"hashtags": [{"tag": "python"}]}'`) without requiring a separate normalized table. For very frequent hashtag queries, a materialized view or a separate `tweet_hashtags` table may be worth the extra write complexity.

**What happens when PostgreSQL starts getting slow at large tweet volumes?**

A few things to check in order: First, make sure your indexes on `created_at` and `keyword` exist — most slow queries on tweet tables are missing these. Second, check if autovacuum is keeping up; high-insert tables accumulate dead tuples. Third, if you're past ~5 million rows, consider partitioning by month on `created_at`. Fourth, for time-series aggregation queries specifically, TimescaleDB's hypertables are worth evaluating — they partition automatically and compress older data, with no changes required to your ingestion code.

**Is it better to use `psycopg2` or `asyncpg` for tweet ingestion?**

For most monitoring pipelines, `psycopg2` is fine and simpler to work with. Use `asyncpg` if you're writing a high-throughput ingestion service where database I/O is genuinely the bottleneck — it's faster on benchmarks because it communicates directly over the Postgres binary protocol. In practice, for pipelines collecting hundreds to low thousands of tweets per minute, `psycopg2` won't be your constraint. API rate limits and network latency will.

**Can I use this setup with multiple keywords at the same time?**

Yes. The `keyword` column in the schema tracks which query produced each tweet. Run separate jobs per keyword (either concurrently or sequentially), all writing to the same database. Tweets that appear in multiple keyword results will be deduplicated on `tweet_id` — only the first job's `keyword` value wins unless you change the conflict resolution to update that field. If a tweet legitimately belongs to multiple keywords, consider a separate `tweet_keywords` junction table instead.