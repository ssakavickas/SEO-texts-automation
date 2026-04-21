# Twitter Monitoring vs Twitter Scraping: What's the Difference?

Most people use these terms interchangeably. They shouldn't. Twitter monitoring and Twitter scraping solve different problems, use different technical approaches, and have very different cost profiles. Picking the wrong one wastes money — or worse, builds a pipeline that silently misses data.

Here's how they actually differ, when to use each, and how the tooling maps to each approach.

## The Core Distinction

**Scraping** is pull-based. You make a request, you get data back. You decide when to ask and how much to retrieve. It's on-demand, episodic, and good for batch or historical work.

**Monitoring** is push-based. You configure a watcher, and data is delivered to you as it happens. The system runs continuously whether you're looking at it or not. It's designed for real-time alerting and ongoing coverage.

The mental model that helps: scraping is like running a search. Monitoring is like setting a trap.

## Side-by-Side Comparison

| Dimension | Scraping | Monitoring |
|---|---|---|
| Data retrieval model | Pull (you request) | Push (delivered to you) |
| Latency | Minutes to hours after posting | Near real-time (seconds) |
| Historical data | Yes | No — watches forward only |
| Continuous coverage | No — gaps between runs | Yes — always on |
| Setup complexity | Low–Medium | Medium |
| Cost model | Per request | Per account per day |
| Best for | Batch analysis, research, one-time pulls | Brand alerts, real-time tracking |

## What Scraping Actually Does

When you scrape Twitter, you're querying for data on demand. You call an endpoint, retrieve a set of tweets, and process them. The job has a clear start and end.

Using [ScrapeBadger's Tweets API](https://scrapebadger.com/docs/twitter/tweets), a scraping workflow looks like this:

```
GET /v1/twitter/tweets/advanced_search
```

You pass a keyword or `from:username` query, get back a paginated set of tweet objects, normalize them, and store them. Done. One credit per request.

That same API gives you several other pull-based operations:

```
GET /v1/twitter/tweets/tweet/{id}           # Full detail on a single tweet
GET /v1/twitter/tweets/tweet/{id}/replies   # Replies thread
GET /v1/twitter/tweets/tweet/{id}/retweeters
GET /v1/twitter/tweets/tweet/{id}/quotes
```

These are useful for deep-dives: analyzing how a specific piece of content spread, pulling reply threads for sentiment work, building datasets for research or model training.

**What scraping is good at:**
- Historical analysis across a date range
- One-time data pulls for a report or dataset
- Batch retrieval across many keywords or accounts
- Pulling engagement data (likers, retweeters, quote tweets) on specific content

**What scraping is bad at:**
- Catching something the moment it's posted
- Continuous coverage without gaps between job runs
- Knowing you missed something

The gap problem is real. If you run a scraping job every 15 minutes, you have 15-minute windows where new tweets exist but haven't been collected. For most use cases, that's fine. For crisis detection or time-sensitive brand monitoring, it isn't.

## What Monitoring Actually Does

Monitoring means setting up a persistent watcher that delivers tweets as they're posted. You define which accounts to watch, configure a webhook URL, and ScrapeBadger handles the rest — including continuous polling, deduplication, and delivery.

The setup is a single API call:

```
POST /v1/twitter/stream/monitors
```

From that point on, when a watched account posts, replies, retweets, or quote-tweets, the payload is delivered to your webhook. You don't poll. You just receive.

You can manage monitors through the [ScrapeBadger Streams API](https://scrapebadger.com/docs/twitter-streams/monitors):

```
GET  /v1/twitter/stream/monitors              # List all active monitors
PATCH /v1/twitter/stream/monitors/{id}        # Add/remove accounts, pause, update filters
DELETE /v1/twitter/stream/monitors/{id}       # Remove a monitor entirely
POST /v1/twitter/stream/webhooks/test         # Verify webhook delivery before going live
```

The delivery and billing logs give you full visibility:

```
GET /v1/twitter/stream/logs           # Tweet delivery history, filterable by monitor or author
GET /v1/twitter/stream/billing-logs   # Per-minute billing ticks for cost auditing
```

**What monitoring is good at:**
- Catching posts within seconds of going live
- Tracking up to 100 accounts per monitor with no polling logic on your end
- Running continuously without scheduled jobs or cron management
- Alerting on new activity from specific known accounts

**What monitoring is bad at:**
- Historical data (it watches forward, not backward)
- Keyword-based search across all of Twitter — it tracks specific accounts, not topics broadly

## Pricing Works Differently

This is where teams often get surprised. Scraping is event-priced. Monitoring is time-priced.

**Scraping:** <span style="color: #2D6A4F; font-weight: bold;">1 credit per request</span>, regardless of idle time.

**Monitoring:** credits accrue per account per day, whether or not those accounts tweet. You're paying for continuous coverage.

| Tier | Accounts | Credits / Account / Day |
|---|---|---|
| Starter | 1–10 | <span style="color: #2D6A4F; font-weight: bold;">1,667</span> |
| Growth | 11–50 | <span style="color: #2D6A4F; font-weight: bold;">1,333</span> |
| Scale | 51–100 | <span style="color: #2D6A4F; font-weight: bold;">1,000</span> |
| Enterprise | 101+ | <span style="color: #2D6A4F; font-weight: bold;">833</span> |

A Starter-tier monitor watching 5 accounts runs approximately <span style="color: #2D6A4F; font-weight: bold;">~250,000 credits/month</span>. If you're only curious about those accounts once a week, scraping the `from:username` endpoint on a schedule is cheaper. If you need to know the second they post, monitoring pays for itself.

## A Practical Gotcha: Shadow-Banned Accounts

If you're scraping using `from:username` on an account that's shadow-banned on Twitter, the search endpoint returns zero results — even if that account is actively posting. This is a scraping-specific limitation.

Monitoring sidesteps this because it watches accounts directly rather than going through search. It's one situation where monitoring is genuinely more reliable than repeated scraping.

## How to Choose

The decision tree is short:

**Use scraping when:**
- You need historical data
- You're doing a batch analysis (keywords, datasets, research)
- You want to pull engagement details on specific tweets
- Cost per insight matters more than latency

**Use monitoring when:**
- You need to know something happened within seconds
- You have a defined set of accounts to watch continuously
- You want zero gaps in coverage
- You're building a real-time alerting or notification system

**Use both when:**
- You want real-time alerts from specific accounts (monitoring) *and* periodic keyword sweeps across broader conversation (scraping)

In practice, most teams end up running both. Monitoring handles the "don't miss this" accounts. Scraping handles the broader keyword and research workflows. They complement each other more than they compete.

## FAQ

**Can I do keyword monitoring with the Streams API?**
No — Stream Monitors track specific accounts (up to 100 per monitor), not keywords. For keyword-based monitoring, the pattern is a scheduled scraping job using the `advanced_search` endpoint.

**What happens to monitoring data if my webhook is down?**
Check the delivery logs at `GET /v1/twitter/stream/logs` — you can see which payloads failed delivery and reprocess them.

**Is scraping legal?**
It depends on jurisdiction, use case, and how the data is stored and used. Always review applicable laws and platform terms before deploying a scraping or monitoring pipeline.

**How do I test my webhook before going live?**
Use `POST /v1/twitter/stream/webhooks/test`. It fires a test payload with `type="test"` so you can verify delivery without waiting for a real tweet.