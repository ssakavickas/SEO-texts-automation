# 📦 ScrapeBadger Content Batch Package

Total Articles: 4
Generated: 2026-03-08 21:03:19

---

## 📄 How to Build a Real-Time Twitter Monitoring Pipeline

# Blog Post Package

## SEO Metadata
Primary Keyword: real-time Twitter monitoring pipeline
Meta Title: Build a Real-Time Twitter Monitoring Pipeline
Meta Description: Learn how to build a real-time Twitter monitoring pipeline using filter rules, WebSockets, and webhooks. Catch brand mentions in seconds, not minutes.


---

## LinkedIn Post
Most Twitter monitoring setups miss what matters most: speed.

A cron job that polls every few minutes is fine for digests. It fails completely when you need to catch a brand crisis, a competitor announcement, or a lead signal within seconds.

Here is how to build a pipeline that actually works in real time.

Key takeaways from the full guide:

- Filter rules use Twitter Advanced Search syntax, so you can monitor exact phrases, specific accounts, minimum engagement thresholds, and language filters from day one
- WebSockets are best for live dashboards needing sub-second updates; webhooks are cleaner for backend pipelines writing to a database or triggering workflows
- Polling intervals directly control cost, Standard tier at one-minute intervals runs about $4.50 per rule per month, while Turbo for crisis detection runs about $45

The guide covers the full implementation: creating rules, connecting via WebSocket with exponential backoff reconnection, verifying webhook signatures, and deduplicating retried deliveries.

Read the full guide: scrapebadger.com

What are you currently using for real-time social monitoring, and what gaps are you running into with your existing setup?

---

## Twitter Thread
Polling for tweets every few minutes is not monitoring. It is just slow search.

- Filter rules push events to you the moment a match is found
- WebSocket for dashboards, webhook for backend pipelines
- Standard tier costs $4.50 per rule per month

Read the full guide: scrapebadger.com

---

# How to Build a Real-Time Twitter Monitoring Pipeline

## Introduction

Most Twitter monitoring setups are pull-based: a cron job fires, fetches recent tweets, stores them, repeats. That works for daily digests. It doesn't work when you need to catch a brand mention within seconds, not minutes.

This guide covers how to build a real-time Twitter monitoring pipeline using ScrapeBadger's streaming infrastructure — filter rules, WebSockets, and webhooks. By the end, you'll have a working system that pushes tweet events to your backend as they happen, not on a polling schedule.

---

## The Two Delivery Models: Pick One

Before writing any code, decide how you want tweet events delivered. ScrapeBadger offers two real-time delivery methods, and they're optimized for different use cases.

| Feature | <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">WebSocket</span> | <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Webhook</span> |
|---|---|---|
| Protocol | Persistent `wss://` connection | HTTP POST callbacks |
| Auth | API key in header or query param | HMAC-SHA256 signature |
| Retries | Client reconnects | 3 automatic retries |
| Max connections | 5 per API key | Unlimited endpoints |
| Best for | Live dashboards, real-time apps | Backend pipelines, storage |

**Rule of thumb:** Use WebSockets for anything user-facing that needs sub-second updates. Use webhooks for backend pipelines where your server receives events and writes them to a database.

---

## Step 1: Create a Filter Rule

A [filter rule](https://scrapebadger.com/docs/twitter-streams/filter-rules) defines what you're monitoring. The moment a tweet matches your rule, it gets pushed to your delivery endpoint.

ScrapeBadger supports Twitter Advanced Search syntax, so you can get precise immediately:

```bash
# Simple keyword
bitcoin OR ethereum

# Original tweets only (no retweets)
#AI -is:retweet

# High-engagement mentions of a specific account
@CompetitorName min_faves:50 -is:retweet

# Exact phrase from a specific account in English
from:elonmusk lang:en "announcement"
```

Before creating a rule, validate it:

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/filter-rules/validate" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "bitcoin OR ethereum -is:retweet"}'
```

Then create the rule:

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/filter-rules" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "bitcoin OR ethereum -is:retweet",
    "tag": "crypto-monitor",
    "interval": "standard"
  }'
```

Rules activate immediately. You can run up to 50 per API key.

---

## Step 2: Choose Your Polling Interval

The polling interval controls how frequently ScrapeBadger checks for new matching tweets. This directly affects cost.

| Tier | Interval | Credits/Rule/Day | Est. Monthly Cost |
|---|---|---|---|
| <span style="background-color: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;">Turbo</span> | 0.5s | 30,000 | ~$45/rule |
| <span style="background-color: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;">Fast</span> | 5s | 10,000 | ~$15/rule |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Standard</span> | 1 min | 1,500 | ~$4.50/rule |
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Relaxed</span> | 10 min | 500 | ~$1.50/rule |
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Daily</span> | 24h | 100 | ~$0.30/rule |

In practice: Standard is the right tier for most monitoring use cases. Turbo is for trading signals or PR crisis detection where seconds matter.

Check current tier pricing via the [filter rules pricing endpoint](https://scrapebadger.com/docs/twitter-streams/filter-rules).

---

## Step 3: Receive Events via WebSocket

Connect once, receive all events for your API key across all active filter rules.

```python
import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30]  # Exponential backoff, capped at 30s

async def handle_message(data: dict):
    if data["type"] != "new_tweet":
        return

    source = data.get("source")        # "filter_rule" or "monitor"
    rule_tag = data.get("rule_tag")    # The tag you set on the rule
    username = data.get("author_username")
    text = data.get("tweet_text")
    latency = data.get("latency_ms")

    logging.info(f"[{rule_tag}] @{username} ({latency}ms): {text[:100]}")
    # → Write to DB, trigger alert, forward to Slack, etc.

async def stream(api_key: str):
    uri = f"wss://[your-domain]/v1/twitter/stream?api_key={api_key}"
    attempt = 0

    while True:
        try:
            async with websockets.connect(uri) as ws:
                logging.info("Connected to stream")
                attempt = 0  # Reset on successful connection
                async for message in ws:
                    data = json.loads(message)
                    await handle_message(data)

        except Exception as e:
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            logging.warning(f"Disconnected: {e}. Reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            attempt += 1

if __name__ == "__main__":
    import os
    asyncio.run(stream(os.getenv("SCRAPEBADGER_API_KEY")))
```

The `rule_tag` field is how you distinguish events from different rules. Set meaningful tags when creating rules — `brand-mentions`, `competitor-launch`, `support-keywords` — so your handler knows what to do with each event.

---

## Step 4: Or Receive Events via Webhook

If you're building a backend pipeline (writing to Postgres, triggering workflows), webhooks are cleaner. ScrapeBadger posts to your endpoint with HMAC-SHA256 signing. Always verify the signature before processing.

```python
from flask import Flask, request, jsonify
import hmac, hashlib, os, logging

app = Flask(__name__)
WEBHOOK_SECRET = os.getenv("SCRAPEBADGER_WEBHOOK_SECRET")

def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    received = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, received)

@app.route("/webhook/twitter", methods=["POST"])
def handle_webhook():
    sig = request.headers.get("X-ScrapeBadger-Signature", "")
    delivery_id = request.headers.get("X-ScrapeBadger-Delivery-Id", "")

    if not verify_signature(request.get_data(), sig):
        return jsonify({"error": "Invalid signature"}), 401

    payload = request.get_json()

    if payload.get("type") == "tweet":
        tweet = payload["tweet"]
        logging.info(
            f"[{delivery_id}] @{payload['author_username']}: "
            f"{tweet['text'][:100]}"
        )
        # → Upsert to DB using tweet_id as primary key
        # → Use delivery_id to deduplicate retried deliveries

    return jsonify({"ok": True}), 200
```

Two things to get right here:

1. Respond with any 2xx status within 10 seconds or ScrapeBadger retries (3 attempts with backoff).
2. Use `X-ScrapeBadger-Delivery-Id` to deduplicate — retries send the same ID, so you can safely ignore already-processed deliveries.

You can test your endpoint before going live via the [webhook test endpoint](https://scrapebadger.com/docs/twitter-streams/webhooks).

---

## What to Do With Events

The pipeline architecture is: filter rule → delivery (WebSocket or webhook) → your handler. The handler is where the actual value lives.

Common patterns:

- **Brand monitoring** → Upsert to Postgres by `tweet_id`, forward high-engagement mentions to Slack
- **Keyword tracking** → Write to a time-series store, build a dashboard showing volume over time
- **Competitor monitoring** → Tag by `rule_tag`, run through a classifier, route to the relevant team channel
- **Lead signals** → Filter for intent phrases (`"looking for alternative"`, `"switching from X"`), push to a CRM queue for manual review

The event payload includes `latency_ms` — the delta between when the tweet was posted and when ScrapeBadger detected it. On Standard tier, expect 60–90 seconds. On Turbo, sub-second.

---

## FAQ

**How many filter rules can I run?**
Up to 50 per API key. Each rule is independent — different queries, different intervals, all delivered to the same WebSocket channel.

**Can I update a rule without deleting it?**
Yes. Use `PATCH /v1/twitter/filter-rules/{rule_id}` to update the query, interval, webhook URL, or status. Changes take effect immediately.

**What happens if my webhook endpoint is down?**
ScrapeBadger retries 3 times with exponential backoff. If all retries fail, the delivery is logged as `webhook_failed`. You can retrieve missed events from the [delivery logs endpoint](https://scrapebadger.com/docs/twitter-streams/filter-rules).

**Is there a way to pause a rule without deleting it?**
Yes — `PATCH` the rule's `status` field to `inactive`. The rule stays configured but stops consuming credits until you reactivate it.

---

## Conclusion

The pipeline is: create a filter rule with a precise query → pick a polling interval that matches your latency requirements → connect via WebSocket or configure a webhook endpoint → handle events in your application.

The parts that matter most are query precision and deduplication. A noisy query generates volume you can't act on. Missing deduplication means duplicated alerts and inflated counts when retries fire.

Start with one rule on Standard tier, validate the signal-to-noise ratio, then expand.

- Docs: [scrapebadger.com/docs/twitter-streams/filter-rules](https://scrapebadger.com/docs/twitter-streams/filter-rules)
- WebSocket reference: [scrapebadger.com/docs/twitter-streams/websocket](https://scrapebadger.com/docs/twitter-streams/websocket)
- Support: [discord.com/invite/3WvwTyWVCx](https://discord.com/invite/3WvwTyWVCx)

---

## 📄 How Startups Use Twitter Monitoring for Lead Generation

# Blog Post Package

## SEO Metadata
Primary Keyword: Twitter monitoring for lead generation
Meta Title: Twitter Monitoring for Lead Generation: Startup Guide
Meta Description: Learn how startups use Twitter monitoring to capture real-time buying signals. Build an automated pipeline that routes warm leads before competitors respond.


---

## LinkedIn Post
Most startups use Twitter to broadcast. The ones generating real leads are doing the opposite.

Right now, someone is tweeting about switching from your competitor or asking for a recommendation in your category. If you respond within an hour, you have a warm conversation. If you see it three days later, you are noise.

The solution is a real-time monitoring pipeline built around buying intent.

Key takeaways from the full guide:

- The three highest-value signals to monitor: direct pain expression, competitor dissatisfaction, and recommendation requests. Everything else is volume, not pipeline.
- Filter rules beat scheduled search scripts. Persistent rules push matching tweets to you the moment they appear, not hours later.
- Noise filtering is the actual work. Excluding retweets, setting engagement minimums, and maintaining a hard exclusion list determines whether your team acts on alerts or ignores them.

Read the full breakdown and technical setup: scrapebadger.com

What buying signals are you currently monitoring for your product category? Drop your approach in the comments.

---

## Twitter Thread
Most startups broadcast on Twitter. The ones winning use it to listen.

- Real-time filter rules catch buying signals the moment they appear
- Tight, intent-focused queries beat broad keywords every time
- Respond within an hour or you are just noise

Read the full guide: scrapebadger.com

---

# How Startups Use Twitter Monitoring for Lead Generation

## Introduction

Most startups treat Twitter like a broadcast channel. They post updates, share links, and wonder why nothing converts. The founders actually generating leads from Twitter are doing the opposite — they're listening, not talking.

The signal is there. Right now, someone is tweeting "does anyone know a good alternative to [your competitor]?" or "so frustrated with [the exact problem your product solves]." If you catch that tweet within an hour and reply with something useful, you have a warm conversation. If you see it three days later, you're noise.

This guide covers how to build an automated Twitter monitoring pipeline that captures buying-intent signals in real time — and routes them somewhere you can act on them.

---

## Why Twitter Works for B2B Lead Generation

The numbers are unambiguous: 82% of B2B companies actively use Twitter for content marketing, and 93% of users who follow SMBs on Twitter plan to purchase from them. More importantly for lead gen, Twitter's conversations are public. Unlike LinkedIn DMs or Slack communities, buying signals on Twitter are findable.

The practical advantage: decision-makers on Twitter are more accessible than on LinkedIn. Competition is lower, conversations move faster, and the cost to participate is zero.

The problem is volume. 500 million tweets go out every day. Manual monitoring at that scale isn't a strategy — it's a way to waste mornings.

---

## The Four Lead Signals Worth Monitoring

Before building anything, be clear about what you're actually looking for. Not all Twitter activity is worth tracking.

| Signal Type | Example Tweet Pattern | Lead Quality |
|---|---|---|
| Direct pain expression | "So frustrated with [problem your product solves]" | <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">High</span> |
| Recommendation request | "Anyone know a good tool for X?" | <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">High</span> |
| Competitor dissatisfaction | "Thinking about switching from [competitor]" | <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">High</span> |
| Category awareness | "Just started evaluating CRMs" | <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Medium</span> |
| Broad industry discussion | General hashtag activity | <span style="background-color: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;">Low</span> |

Focus on the top three. The bottom two generate volume, not pipeline.

---

## Building the Monitoring Pipeline

### Step 1: Set Up Real-Time Filter Rules

The most reliable approach is using the [ScrapeBadger Filter Rules API](https://scrapebadger.com/docs/twitter-streams/filter-rules) to create persistent monitoring rules that run 24/7. Unlike scheduled search scripts, filter rules push matching tweets to you the moment they appear.

```bash
# Create a filter rule via the API
curl -X POST "https://scrapebadger.com/v1/twitter/filter-rules" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "\"looking for a CRM\" -is:retweet lang:en",
    "polling_interval": "1m",
    "webhook_url": "https://your-app.com/webhooks/twitter"
  }'
```

You can validate query syntax before activating a rule with `POST /v1/twitter/filter-rules/validate` — worth doing before spending credits on a malformed query.

**Polling tier selection:** For most startups, the <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Standard tier</span> (1-minute polling at ~$4.50/month per rule) is the practical starting point. Turbo polling (0.5-second intervals) makes sense only if response time is a critical differentiator for you.

| Tier | Poll Interval | Credits/Rule/Day | Best For |
|---|---|---|---|
| Turbo | 0.5 sec | 30,000 | Time-critical monitoring |
| Fast | 5 sec | 10,000 | High-value keywords |
| **Standard** | **1 min** | **1,500** | **Most startup use cases** |
| Relaxed | 10 min | 500 | Background tracking |
| Daily | 24 hrs | 100 | Low-priority signals |

### Step 2: Write High-Signal Queries

The query is where most pipelines fail. Broad keywords return noise. Tight, intent-focused queries return leads.

```
# Recommendation requests
"recommend a tool for" lang:en -is:retweet min_faves:2

# Competitor switching signals
"alternative to [competitor]" OR "switching from [competitor]" -is:retweet

# Active evaluation signals
"evaluating" OR "shortlisting" "[your category]" -is:retweet lang:en

# Direct frustration signals
"frustrated with [competitor]" OR "hate [competitor]" -is:retweet
```

One constraint worth knowing: if a `from:username` query returns zero results for an account you know is active, that account may be shadow-banned. Twitter suppresses tweet distribution from those accounts — don't waste a monitoring rule on them.

### Step 3: Receive Alerts via Webhook

When a filter rule matches a tweet, ScrapeBadger POSTs it to your webhook endpoint. The payload gives you everything you need to evaluate the lead:

```json
{
  "type": "tweet",
  "tweet_id": "1234567890123456789",
  "author_username": "prospecthandle",
  "detected_at": "2026-03-04T12:00:00.850Z",
  "tweet": {
    "text": "Anyone know a good alternative to HubSpot for a 10-person startup?",
    "favorite_count": 3,
    "reply_count": 7
  }
}
```

Verify webhook authenticity using the `X-ScrapeBadger-Signature` header (HMAC-SHA256). ScrapeBadger retries delivery 3 times with exponential backoff if your endpoint is temporarily unavailable, and you can use `X-ScrapeBadger-Delivery-Id` to deduplicate on your side.

```python
import hmac, hashlib

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, received)
```

### Step 4: Mine Engagement Data for Warm Leads

Beyond keyword monitoring, the [Tweets API](https://scrapebadger.com/docs/twitter/tweets) lets you pull engagement data from specific tweets — a useful source of pre-qualified leads.

If a competitor just announced a new pricing change and the tweet has 200 replies, those repliers are worth looking at:

```bash
# Get everyone who replied to a specific tweet
GET /v1/twitter/tweets/tweet/{id}/replies

# Get users who retweeted a competitor's product announcement
GET /v1/twitter/tweets/tweet/{id}/retweeters

# Get users who liked — lower intent, but useful for volume
GET /v1/twitter/tweets/tweet/{id}/favoriters
```

People engaging with a competitor's pricing announcement are, by definition, aware of the category and evaluating options. That's a warm list, not a cold one.

---

## Noise Filtering: The Work That Actually Matters

Raw monitoring output is always noisy. The signal-to-noise ratio determines whether your team actually acts on alerts or starts ignoring them.

Build these filters into your pipeline from day one:

- **Exclude retweets.** Add `-is:retweet` to every query. Retweets almost never surface new buying intent.
- **Set engagement minimums.** Ignore tweets with zero engagement unless they're from accounts you've specifically targeted. `min_faves:2` cuts a lot of spam.
- **Filter by language.** If you operate in English markets, `lang:en` reduces volume 40–60% without losing relevant leads.
- **Maintain a hard exclusion list.** Add `(-giveaway -contest -airdrop -crypto)` to queries from the start. These terms generate constant false positives.

After two weeks, audit your captured data. If less than 30% is actionable, tighten your queries.

---

## What to Do When You Get a Match

The pipeline catches the signal. Humans decide how to respond. A few things that actually work:

- **Reply publicly first.** If the tweet is a question or complaint, a genuine public reply builds credibility with everyone who sees the thread — not just the original author.
- **Respond within an hour.** Leads cool fast on Twitter. A same-day reply to a buying signal tweet still lands reasonably well. A 48-hour reply is noise.
- **Personalize from the tweet.** "Saw you're evaluating options for [specific thing they mentioned]" outperforms any generic opener.
- **Don't pitch immediately.** Offer something useful first — a relevant resource, an honest comparison, an answer to their actual question.

---

## FAQ

**How many filter rules do I need to start?**
Start with 3–5. One for direct pain signals, one for competitor dissatisfaction, one for recommendation requests. Add more after you've validated signal quality on the first set. ScrapeBadger supports up to 50 rules per API key.

**What's the realistic cost for a startup?**
At Standard tier polling, one filter rule costs roughly $4.50/month. Five rules is ~$22/month. Add the cost of tweet search credits for the engagement mining endpoints, and most startups run this for under $50/month total.

**Can I connect this to my CRM?**
Yes. The webhook payload is standard JSON — route it through n8n, Zapier, or a simple Python function to create contacts in HubSpot, Salesforce, or Pipedrive with the tweet context attached.

**What if I'm getting too many false positives?**
Add `min_faves:3` or `min_replies:1` to your query to filter for tweets with at least minimal engagement. Also review your query for ambiguous terms and add more negative keywords.

---

## Conclusion

Twitter monitoring for lead generation is a data engineering problem dressed up as a marketing question. The startups doing it well have built a simple pipeline: define high-intent queries → capture matching tweets in real time → filter noise → route to humans who respond fast.

The [Filter Rules API](https://scrapebadger.com/docs/twitter-streams/filter-rules) handles the hard part. The queries and the response playbook are yours to own.

Start with one query targeting the clearest buying signal in your category. Get the webhook wired up, validate the signal quality for two weeks, then expand from there.

---

## 📄 Twitter Monitoring vs Twitter Scraping: What’s the Difference?

# Blog Post Package

## SEO Metadata
Primary Keyword: Twitter monitoring vs Twitter scraping
Meta Title: Twitter Monitoring vs Scraping: Key Differences
Meta Description: Twitter scraping pulls data on demand; monitoring delivers real-time alerts. Learn which tool fits your use case and how to use both effectively.


---

## LinkedIn Post
Most people use "Twitter scraping" and "Twitter monitoring" as if they mean the same thing. They do not.

Picking the wrong one costs you time, money, and complexity you never needed.

Here is what actually separates them:

- Scraping is pull-based. You ask a question, you get an answer. Use it for audits, one-time keyword sweeps, or pulling engagement data on a specific tweet.
- Monitoring is push-based. You define what to watch, and the system alerts you the moment it happens. Use it for real-time brand tracking, competitor alerts, and webhook-driven workflows.
- Most serious workflows use both. Scrape first to build a historical baseline, then switch to monitoring for ongoing coverage.

The decision rule is simple: if you are asking a question on-demand, scrape. If you need to know the moment something happens, monitor.

Read the full breakdown at scrapebadger.com

Which approach does your team rely on more heavily right now, and what made you default to it?

---

## Twitter Thread
Scraping and monitoring are not the same thing. Confusing them is expensive.

- Scraping = pull data on demand, great for audits and research
- Monitoring = get alerted the moment something happens, built for real-time
- Most workflows need both, not one or the other

Read the full guide: scrapebadger.com

---

# Twitter Monitoring vs Twitter Scraping: What's the Difference?

## Introduction

These two terms get used interchangeably. They shouldn't be.

Twitter scraping and Twitter monitoring solve different problems, use different mechanisms, and cost differently. Conflating them leads to picking the wrong tool — usually the more expensive or complex one — for a job that didn't need it.

Here's a clear breakdown of what each actually does, when to use which, and how they map to real API features.

---

## The Core Difference

**Twitter scraping** is pull-based. You make a request, you get data back. It's on-demand — useful for looking up a specific tweet, pulling a user's recent posts, or searching for keyword mentions at a point in time.

**Twitter monitoring** is push-based. You define what you want to watch, and the system continuously polls or streams that data to you. You don't ask — you get notified.

| Factor | Scraping | Monitoring |
|---|---|---|
| **How it works** | You call the API when you need data | System watches continuously, delivers to you |
| **Latency** | On-demand (seconds) | Near real-time (down to 0.5s polling) |
| **Historical data** | ✅ Yes | ❌ No — forward-looking only |
| **Webhooks** | ❌ No | ✅ Yes |
| **Billing model** | Per request | Per account/rule per day |
| **Best for** | Research, batch lookups, audits | Live alerts, brand tracking, real-time signals |

---

## When You Want Scraping

Scraping is the right tool when you have a specific question and need an answer now.

**Example situations:**
- You see a tweet go viral and want to pull all its retweeters
- You're auditing a competitor's last 100 posts
- You're doing a one-time keyword sweep before a product launch
- You need the full engagement breakdown on a specific tweet ID

The [ScrapeBadger Tweets API](https://scrapebadger.com/docs/twitter/tweets) covers this. One credit per request, 180 requests per 15-minute window.

Key endpoints worth knowing:

| Endpoint | What It Does |
|---|---|
| `GET /v1/twitter/tweets/tweet/{id}` | Full tweet details — author, engagement, media, edit history |
| `GET /v1/twitter/tweets/advanced_search` | Keyword and hashtag search with full query syntax |
| `GET /v1/twitter/tweets/tweet/{id}/retweeters` | Paginated list of users who retweeted a tweet |
| `GET /v1/twitter/tweets/tweet/{id}/replies` | Replies to a specific tweet |
| `GET /v1/twitter/tweets/tweet/{id}/quotes` | Quote tweets — useful for tracking content spread |

The `advanced_search` endpoint supports Twitter's full query syntax. For example:

```
"CompetitorBrand" -from:competitorhandle   # What others say about them
from:competitor -is:retweet                # Their original posts only
#ProductLaunch min_faves:50               # High-engagement campaign tweets
```

> **Note:** If `from:username` returns nothing for an account you know is active, that account may be shadow-banned. Verify at `x.com/search?q=from%3AUSERNAME&src=typed_query&f=live` before assuming a data problem.

Scraping is also how you backfill. If you're setting up a competitor tracking workflow and want a baseline — what did they post over the last 90 days, which tweets got the most engagement — scraping is how you get that historical dataset before switching to monitoring for ongoing coverage.

---

## When You Want Monitoring

Monitoring is the right tool when the question is "tell me when something happens" rather than "give me what happened."

**Example situations:**
- You want an alert every time a competitor posts anything
- You're watching for mentions of your brand in real-time
- You need a webhook to fire when a specific keyword appears

Two distinct features cover this on ScrapeBadger:

### Stream Monitors

[Stream Monitors](https://scrapebadger.com/docs/twitter-streams/monitors) watch specific Twitter accounts. You add up to 100 accounts per monitor, and ScrapeBadger triggers immediately when any of them tweets, replies, retweets, or quote-tweets.

Pricing scales with account volume:

| Tier | Accounts | Credits/Account/Day | Est. Monthly (5 accounts) |
|---|---|---|---|
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Starter</span> | 1–10 | 1,667 | ~$25/mo |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Growth</span> | 11–50 | 1,333 | — |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Scale</span> | 51–100 | 1,000 | — |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Enterprise</span> | 101+ | 833 | — |

Useful endpoints:

```
POST /v1/twitter/stream/monitors        # Create a monitor (starts immediately)
PATCH /v1/twitter/stream/monitors/{id}  # Update accounts, pause, resume
POST /v1/twitter/stream/webhooks        # Configure delivery URL
POST /v1/twitter/stream/webhooks/test   # Verify webhook works before going live
GET  /v1/twitter/stream/logs            # View delivery history
```

### Filter Rules

[Filter Rules](https://scrapebadger.com/docs/twitter-streams/filter-rules) watch for search queries rather than specific accounts. You define a keyword, hashtag, or any advanced search expression, set a polling interval, and ScrapeBadger delivers matching tweets to your webhook.

Up to 50 rules per API key. Pricing is based on polling frequency:

| Tier | Polling Interval | Credits/Rule/Day | Est. Monthly |
|---|---|---|---|
| <span style="background-color: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;">Turbo</span> | Every 0.5s | 30,000 | ~$90/mo |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Fast</span> | Every 5s | 10,000 | ~$30/mo |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Standard</span> | Every 1 min | 1,500 | ~$4.50/mo |
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Relaxed</span> | Every 10 min | 500 | ~$1.50/mo |
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Daily</span> | Every 24h | 100 | ~$0.30/mo |

Example queries for competitor tracking:

```
"CompetitorName" -is:retweet     # Original mentions only
from:competitor_handle           # Everything they post
#TheirProductHashtag min_faves:10
```

Validate your query syntax before creating a rule:

```
POST /v1/twitter/filter-rules/validate
```

This catches errors (bad quotes, unsupported operators, length limits) before you're billed.

---

## Which One Do You Actually Need?

In practice, most real workflows use both. The decision comes down to what question you're answering.

| Use Case | Right Tool |
|---|---|
| Pull a competitor's last 100 tweets | Scraping (Tweets API) |
| Get alerted the moment a competitor posts | Monitoring (Stream Monitor) |
| Search for brand mentions right now | Scraping (advanced_search) |
| Get a webhook when your keyword appears | Monitoring (Filter Rule) |
| Historical keyword sweep for research | Scraping |
| Real-time brand mention alerts | Monitoring |
| Audit a specific tweet's engagement | Scraping |
| Watch 20 competitors continuously | Monitoring (Stream Monitor) |

**Decision rule:** If you're asking a question you'll ask once or on-demand, use scraping. If you need to know the moment something happens, use monitoring.

Polling frequency matters too. A PR team watching for a crisis needs Turbo or Fast. A market research team running weekly reports can use Daily without sacrificing anything.

---

## FAQ

**Can I do competitor tracking with scraping instead of monitoring?**
Yes, but it means running scheduled jobs yourself — cron + the Tweets API, deduplicating results, managing gaps. Monitoring offloads that polling logic entirely. For active tracking of 5+ accounts, the Stream Monitor is cleaner and more reliable than DIY cron jobs.

**Does monitoring give me historical data?**
No. Monitors and filter rules are forward-looking only. If you want historical context before starting a monitor, backfill with the Tweets API first, then switch to monitoring for ongoing coverage.

**What's the latency on Filter Rules?**
Depends on the tier. Turbo (0.5s polling) is as close to real-time as you'll get without a direct firehose. Standard (1 min) is fine for most brand and keyword tracking. Daily is appropriate for low-frequency research queries.

---

## Conclusion

Scraping answers questions. Monitoring catches events.

Both are legitimate, and both use structured, clean data through the [ScrapeBadger API](https://scrapebadger.com/docs/twitter/tweets) — no proxy maintenance, no headless browsers, no scrapers breaking when Twitter changes its frontend. The infrastructure layer is handled. Your job is picking the right mechanism for the right use case.

Start with scraping to validate your data. Switch to monitoring when you need things to happen automatically.

---

## 📄 How to Detect Viral Trends Early Using Twitter Streams

# Blog Post Package

## SEO Metadata
Primary Keyword: detect viral trends early Twitter streams
Meta Title: Detect Viral Trends Early Using Twitter Streams
Meta Description: Learn how to detect viral trends early using Twitter streams before they hit the Trending tab. Set up real-time filters, velocity alerts, and WebSocket pipelines.


---

## LinkedIn Post
By the time a topic hits Twitter's Trending tab, the opportunity is already gone.

The platform's own algorithm detects trends reactively. Teams that win are watching the stream before the spike, not after it.

Research from MIT shows a well-designed detection system can identify trending topics 1.43 hours earlier than Twitter's native algorithm. That lead time is the difference between organic reach and noise.

Here is what actually matters:

- Velocity beats volume. A keyword posting 200% more tweets per hour than its 24-hour baseline is your real alert signal.
- Source diversity and retweet-to-original ratios reveal whether a spike is genuine or manufactured.
- Joining a trend within the first two hours increases reach by 340%, according to published studies.

The full guide walks through a practical six-step pipeline: pulling trend baselines, building real-time filter rules, receiving live data via WebSocket, and dynamically upgrading polling speed as a topic accelerates.

Read the full guide: scrapebadger.com

Are you monitoring for trends reactively or proactively? What tools or signals does your team rely on to catch early momentum?

---

## Twitter Thread
By the time something hits Trending, you have already lost the window.

- Velocity, not volume, is the real signal
- MIT research shows 1.43 hrs of lead time is achievable
- Early entry boosts reach by 340%

Read the full guide: scrapebadger.com

---

# How to Detect Viral Trends Early Using Twitter Streams

## Introduction

By the time a topic hits Twitter's official Trending tab, you've already missed the early window. The platform's own algorithm detects trends reactively — measuring sharp spikes in volume and velocity, then surfacing them after the fact. Teams that catch trends early are monitoring the stream *before* the spike, not after.

This guide covers how to detect viral trends early using Twitter streams: what signals actually matter, how to structure a real-time monitoring pipeline, and which endpoints to use at each stage.

---

## Why the Trending Tab Is Already Too Late

Twitter's trending algorithm prioritizes velocity over volume. A topic generating 10,000 tweets in one hour trends faster than one generating 50,000 over several days. That's the design — it reflects what people are talking about *more right now* than a minute ago.

Research from MIT confirms this lag: a well-designed detection system can identify trending topics **1.43 hours earlier than Twitter's own algorithm**, with 95% accuracy and a 4% false positive rate. The early signal exists in the data stream — you just need to be watching the right place.

By the time something appears in Explore, three things have already happened:

- The velocity spike has already peaked
- Early participants have captured the organic reach boost (studies show joining within the first two hours increases reach by 340%)
- The conversation has shifted from niche to mainstream, reducing relevance for specialized audiences

---

## The Two Signals That Actually Matter

Before building anything, get clear on what you're measuring.

**Volume** is how many tweets mention a topic in a given window. **Velocity** is how fast that volume is accumulating. Twitter trends on velocity, not volume.

A practical threshold to flag: a keyword posting >200% more tweets per hour than its baseline over the previous 24 hours. That's the signal worth alerting on — not absolute tweet count.

Secondary signals worth tracking:

- **Source diversity** — is the spike coming from one account or hundreds?
- **Retweet-to-original ratio** — high RT ratio means content is spreading, not just being posted
- **Engagement from non-followers** — a reliable indicator that a topic is escaping its niche

---

## Step 1: Check What's Already Trending (Baseline)

Start by pulling the current trending snapshot for your target locations. This gives you a baseline to compare against as you monitor the stream.

Use the [Trends endpoints](https://scrapebadger.com/docs/twitter/trends):

| Endpoint | What It Does |
|---|---|
| `GET /v1/twitter/trends/place/{woeid}` | Trending topics for a specific location |
| `GET /v1/twitter/trends/` | Trending for the authenticated user's location |
| `GET /v1/twitter/trends/locations` | Full list of available WOEIDs |

Common WOEIDs for trend targeting:

| Location | WOEID |
|---|---|
| Worldwide | `1` |
| United States | `23424977` |
| United Kingdom | `23424975` |
| New York | `2459115` |

Run this on a schedule (hourly is sufficient) to track what's already surfaced. Anything you detect in your stream before it appears here is genuine early signal.

---

## Step 2: Set Up Real-Time Filter Rules

This is the core detection layer. [Filter rules](https://scrapebadger.com/docs/twitter-streams/filter-rules) let you define keyword queries that ScrapeBadger monitors in real time. When a tweet matches, it's delivered to you immediately — no polling on your end.

Validate your query before committing credits:

```
POST /v1/twitter/filter-rules/validate
```

Then create the rule:

```
POST /v1/twitter/filter-rules
```

### Query Patterns for Early Trend Detection

Use Twitter's Advanced Search syntax. A few patterns that work in practice:

```
# Hashtag velocity monitoring — original posts only
#AI -is:retweet

# Catch spikes around a topic before it gets a hashtag
"bitcoin" OR "crypto" -is:retweet lang:en

# High-engagement filter to surface breakout content early
"breaking" min_faves:50 -is:retweet

# Monitor a niche community for signals before mainstream pickup
from:TechCrunch OR from:benedictevans OR from:stratechery
```

### Polling Interval: Match Speed to Urgency

The interval you choose determines how fast you catch the signal. Faster = more credits per day.

| Tier | Interval | Credits/Rule/Day | Use Case |
|---|---|---|---|
| <span style="background-color: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;">Turbo</span> | 0.5s | 30,000 | Breaking news, live events |
| <span style="background-color: #dcfce7; padding: 2px 4px; border-radius: 4px; color: #166534;">Fast</span> | 5s | 10,000 | Near real-time trend detection |
| <span style="background-color: #dbeafe; padding: 2px 4px; border-radius: 4px; color: #1e40af;">Standard</span> | 1 min | 1,500 | General keyword monitoring |
| Relaxed | 10 min | 500 | Low-priority background tracking |

For early trend detection, **Fast** is the practical starting point. Turbo is worth it only for live events where minutes matter.

---

## Step 3: Receive Matches via WebSocket

Rather than polling an endpoint, connect via [WebSocket](https://scrapebadger.com/docs/twitter-streams/websocket) to receive matching tweets pushed to you as they're detected.

```python
import asyncio, json, websockets

async def stream():
    uri = "wss://[your-domain]/v1/twitter/stream?api_key=YOUR_API_KEY"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "new_tweet":
                print(f"@{data['author_username']}: {data['tweet_text']}")
                print(f"Latency: {data['latency_ms']}ms")

asyncio.run(stream())
```

The `latency_ms` field in each payload tells you how quickly your system is catching content after it's posted. For trend detection, aim to keep this under 2,000ms on Fast tier.

Each `new_tweet` event includes `rule_id` and `rule_tag` — so if you're running multiple keyword rules simultaneously, you can immediately route events to the right downstream handler without re-parsing the content.

---

## Step 4: Count, Compare, Alert

Raw tweet delivery isn't trend detection — it's data collection. The detection layer sits on top.

A minimal velocity counter in Python:

```python
from collections import defaultdict
from datetime import datetime, timedelta

tweet_counts = defaultdict(list)  # rule_tag → list of timestamps

def on_tweet(rule_tag: str):
    now = datetime.utcnow()
    tweet_counts[rule_tag].append(now)
    # Keep only the last 60 minutes
    tweet_counts[rule_tag] = [
        t for t in tweet_counts[rule_tag]
        if t > now - timedelta(hours=1)
    ]
    current_velocity = len(tweet_counts[rule_tag])
    return current_velocity
```

Set a baseline per keyword (average hourly count over the previous 24 hours) and alert when the current window exceeds 2× that baseline. That's your early signal threshold.

---

## Step 5: Upgrade Polling Speed as a Trend Accelerates

One underused capability: you can update a rule's polling interval mid-stream without deleting and recreating it.

```
PATCH /v1/twitter/filter-rules/{rule_id}
```

In practice: start keywords on Standard tier (1 min / 1,500 credits/day). When velocity crosses your alert threshold, upgrade that specific rule to Fast or Turbo. This keeps baseline costs low while giving you high-resolution data on the topics actually breaking through.

---

## Workflow Summary

| Step | Action | Endpoint |
|---|---|---|
| 1 | Pull trending snapshot as baseline | `GET /v1/twitter/trends/place/{woeid}` |
| 2 | Validate query before creating rule | `POST /v1/twitter/filter-rules/validate` |
| 3 | Create filter rule for target keywords | `POST /v1/twitter/filter-rules` |
| 4 | Connect WebSocket for live push delivery | `wss://[domain]/v1/twitter/stream` |
| 5 | Count velocity, compare to baseline, alert | Your application layer |
| 6 | Upgrade polling speed when trend accelerates | `PATCH /v1/twitter/filter-rules/{rule_id}` |
| 7 | Review delivery logs to audit capture rate | `GET /v1/twitter/filter-rules/{rule_id}/logs` |

---

## What to Do When You Detect a Spike

Early detection only pays off if you act on it. A few things that compound the advantage:

- **Post original content on the topic immediately** — the 340% reach boost from early participation is real
- **Route the alert to a Slack channel** so the right person sees it within minutes, not hours
- **Tag the matched tweets by topic** in your database — you'll want the historical data to spot recurring patterns

For [Twitter scraping](https://scrapebadger.com/docs/twitter) at scale across multiple keyword clusters, keep rules focused. Fifty narrow rules outperform five broad ones — both for accuracy and for routing matched tweets to the right downstream workflow.

---

## FAQ

**How early can I realistically detect a trend before it hits the Trending tab?**
Research shows 45 minutes to 1.5 hours of lead time is achievable with velocity-based detection. Your actual window depends on how tight your alert threshold is and how fast your polling interval is set.

**How many filter rules can I run simultaneously?**
Up to 50 per API key. Run them at lower polling tiers by default; upgrade specific rules dynamically when a topic accelerates.

**Do I need to handle reconnection logic for the WebSocket?**
Yes. Implement exponential backoff on disconnect — network interruptions will happen, and an unhandled disconnect means missed data during a spike, which is exactly when you need coverage most.

---

