# How to Track Competitors on Twitter (X) Without the Official API

Twitter's official API costs $5,000/month for Pro access. Most teams tracking competitors don't need that — they need a handful of signals: what competitors are posting, when their audience is growing, and when they announce something important. Here's how to get all of that without the invoice.

## What You're Actually Trying to Learn

Before picking a method, be specific about what data matters. Most teams care about three things:

**Content patterns** — posting frequency, content formats, hashtags, and what drives engagement. Tells you what's working in your market.

**Audience growth** — follower velocity and who's engaging. A competitor gaining 10,000 followers from a specific vertical is a signal worth investigating.

**Strategic moves** — product launches, partnerships, pricing changes. These hit Twitter before press releases do. Real-time monitoring catches moves 10–15 days before quarterly reports.

The goal is faster differentiation, not copying tactics.

## Method 1: Twitter Lists + TweetDeck (Free, Zero Setup)

Start here if your budget is zero.

Create a **private Twitter List** with all competitor accounts — company handle, executive accounts, product team, customer support. Private lists are invisible to competitors.

Configure TweetDeck columns: one per competitor handle, one for keyword searches. Enable browser notifications on critical accounts so you catch announcements immediately.

Use Boolean operators to cut noise:

```
(competitor1 OR competitor2) AND (launch OR update OR partnership) -giveaway -contest
```

**Limitations:** no persistent storage, no historical data, requires manual review. Fine for 3–5 competitors checked weekly. Falls apart beyond that.

## Method 2: Third-Party Scraping APIs (Programmatic, Scalable)

This is the workhorse approach for teams that want persistent, automated tracking without maintaining their own scraper.

[ScrapeBadger's Twitter API](https://scrapebadger.com/docs/twitter) covers 39 endpoints — competitor profiles, timelines, follower lists, engagement data, and keyword search. Credit-based pricing at $0.10 per 1,000 items.

### Pull a Competitor's Profile

```python
import asyncio
import os
from scrapebadger import ScrapeBadger

async def get_competitor_profile(username: str):
    async with ScrapeBadger(api_key=os.getenv("SCRAPEBADGER_API_KEY")) as client:
        # Full profile: follower count, bio, verification status
        profile = await client.twitter.users.by_username(username)
        print(profile)

asyncio.run(get_competitor_profile("competitor_handle"))
```

Relevant endpoints from the [Users API](https://scrapebadger.com/docs/twitter/users):

| Endpoint | What it returns |
|---|---|
| `/v1/twitter/users/{username}/by_username` | Full profile: bio, follower count, verification |
| `/v1/twitter/users/{username}/about` | Account history, username changes, provenance |
| `/v1/twitter/users/{username}/latest_tweets` | Most recent tweets, paginated |
| `/v1/twitter/users/{username}/followers` | Full follower list |
| `/v1/twitter/users/{username}/latest_followers` | Most recently gained followers |

### Track Their Timeline on a Schedule

```python
async def track_competitor_tweets(handle: str, max_items: int = 100):
    async with ScrapeBadger(api_key=os.getenv("SCRAPEBADGER_API_KEY")) as client:
        stream = client.twitter.users.latest_tweets(handle, max_items=max_items)
        results = []
        async for tweet in stream:
            metrics = tweet.get("public_metrics") or {}
            results.append({
                "id": tweet.get("id"),
                "text": tweet.get("text"),
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "created_at": tweet.get("created_at"),
            })
        return results
```

Run this daily via cron and store results in SQLite. After two weeks, you have a trend dataset — posting frequency, average engagement per post, which content formats are working.

### Search for Competitor Mentions

The [`advanced_search` endpoint](https://scrapebadger.com/docs/twitter/tweets) accepts full query syntax:

```
"CompetitorBrand" -from:competitorhandle    # What others say about them
from:competitorhandle -is:retweet           # Only their original content
#CompetitorCampaign min_faves:50            # High-engagement campaign tweets
```

> ⚠️ **Shadow-ban check:** If `from:username` returns nothing for an active account, they may be shadow-banned. Verify first: `https://x.com/search?q=from%3AUSERNAME&src=typed_query&f=live`. Shadow-banned accounts also won't deliver events through stream monitors.

## Method 3: Real-Time Monitoring with Stream Monitors

Polling on a schedule works for daily analysis. For real-time alerts — when a competitor announces something important — you want a webhook that fires the moment they tweet.

ScrapeBadger's [Stream Monitors](https://scrapebadger.com/docs/twitter-streams/monitors) handle this. One monitor can track up to 100 accounts simultaneously and fires a webhook on tweets, replies, retweets, and quote tweets.

```bash
# Create a monitor for competitor accounts
curl -X POST "https://scrapebadger.com/v1/twitter/stream/monitors" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "usernames": ["competitor1", "competitor2", "competitor3"],
    "filter_types": ["tweets", "retweets", "replies"]
  }'
```

Then attach a webhook to receive events:

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/stream/webhooks" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"monitor_id": "YOUR_MONITOR_ID", "url": "https://yourapp.com/webhook"}'
```

Test it before relying on it in production:

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/stream/webhooks/test" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"monitor_id": "YOUR_MONITOR_ID"}'
```

Monitor pricing is per-account-per-day:

| Tier | Accounts | <span style="color: #2D6A4F; font-weight: bold;">Credits/Account/Day</span> |
|---|---|---|
| Starter | 1–10 | 1,667 |
| Growth | 11–50 | 1,333 |
| Scale | 51–100 | 1,000 |
| Enterprise | 101+ | 833 |

For most teams tracking 5–10 competitors, the Starter tier handles it cleanly.

## Method 4: No-Code Platforms (n8n, Make, Zapier)

If you don't want to write code, n8n + ScrapeBadger works well. A scheduled trigger calls the ScrapeBadger API via an HTTP Request node, a Split Out node separates individual tweets, and you route results to Slack, Airtable, or a Google Sheet.

[Full walkthrough here](https://scrapebadger.com/blog/how-to-scrape-twitterx-tweets-with-n8n-using-scrapebadger-and-send-the-data-anywhere). Setup takes under an hour.

## Comparison: Which Method Fits Your Situation

| Method | Setup Time | Maintenance | Cost | Best For |
|---|---|---|---|---|
| Twitter Lists + TweetDeck | Minutes | Manual | $0 | Casual monitoring, 3–5 competitors |
| Scraping API (ScrapeBadger) | Hours | Low | $10–50/mo | Developers building custom pipelines |
| Stream Monitors + Webhooks | Hours | Low | Per-account/day | Real-time alerts on competitor activity |
| No-code (n8n + ScrapeBadger) | Hours | Low | $10–30/mo | Non-technical teams, quick setup |
| Social listening platforms | Hours | Low | $200–500/mo | Marketing teams needing multi-platform reports |

## Metrics Worth Tracking

Not everything is worth measuring. Focus on what changes decisions:

- **Posting frequency and timing** — reveals content calendar patterns
- **Engagement rate per post** — sudden spikes signal campaigns worth studying
- **Follower velocity** — growth rate per week distinguishes organic from paid
- **Latest followers** — who's following them recently tells you which audiences they're winning
- **Quote tweet spread** — use [`/v1/twitter/tweets/{id}/quotes`](https://scrapebadger.com/docs/twitter/tweets) to track how competitor content propagates

Export weekly. Look for 30–90 day trends, not daily noise.

## Practical Starting Point

Pick the method that matches your current situation. Non-technical teams: start with n8n and get something running today. Developers: start with ScrapeBadger's `latest_tweets` endpoint and a SQLite store — the [docs](https://scrapebadger.com/docs/twitter/users) cover all endpoints with examples. Solo operators: TweetDeck + Boolean search for free.

Run a 30-day pilot tracking 3–5 competitors before scaling. Measure how often the data actually influences a decision. If it does, expand scope. If you're collecting data nobody reads, narrow the focus.

Tracking only works if it changes what you do next.