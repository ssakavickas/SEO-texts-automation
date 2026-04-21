# Blog Post Package

## SEO Metadata
Primary Keyword: detect viral trends Twitter
Meta Title: Detect Viral Twitter Trends Early With Streaming APIs
Meta Description: Learn how to detect viral Twitter trends before they peak using velocity signals, filter rules, and WebSocket streams. Build a real-time trend detection pipeline today.


---

## LinkedIn Post
Most teams find out about trending topics the same way everyone else does — after the conversation has already peaked.

That is not trend intelligence. That is catching the tail end of something that broke hours ago.

The teams that actually benefit are the ones who detect velocity spikes before a topic goes mainstream. Here is what that looks like in practice:

- Velocity beats volume. A hashtag jumping from 50 to 500 mentions in 15 minutes is a stronger early signal than a topic with 10,000 steady daily mentions.
- Two layers matter. Streaming filter rules catch spikes early. The Trends API confirms a topic has broken through. Use both, in that order.
- Noise filtering is where most pipelines fail. Filtering out retweets, setting minimum engagement thresholds, and tracking source diversity separates real signals from coordinated bot activity.

MIT research showed velocity-based detection can identify trends an average of 1.43 hours before Twitter's own algorithm. The methodology still holds.

The full implementation guide, including the WebSocket setup, velocity counter code, and polling tier breakdown, is at scrapebadger.com.

What signals are you currently using to catch trends early? Are you monitoring velocity, or still relying on the Trending tab?

---

## Twitter Thread
Most teams find trends after they peak. Here is how to get there first.

- Measure velocity, not volume
- Use streaming rules to catch spikes before trending lists catch up
- Filter retweets and bots or your alerts are noise

Read the full guide: scrapebadger.com

---

# How to Detect Viral Trends Early Using Twitter Streams

Most teams discover trending topics the same way everyone else does — by checking the Trending tab after the conversation has already peaked. By the time a topic appears there, you're not early. You're catching the tail end of something that broke hours ago.

The teams that actually benefit from trend intelligence aren't faster at reading the Trending tab. They've built pipelines that detect velocity spikes *before* a topic goes mainstream. This guide covers how to do that in practice — the signals that matter, the tools that work, and a concrete implementation using ScrapeBadger's streaming API.

## Why Twitter Is Still the Right Signal Source

Twitter/X processes around 500 million tweets per day. The platform's real value for trend detection isn't volume — it's velocity. A hashtag that jumps from zero to 5,000 mentions in an hour carries more signal than one generating a steady 50,000 over a week. That distinction is why Twitter remains the fastest source for breaking topics, even as the official API has become harder to access affordably.

The research backs this up. MIT researchers demonstrated in 2012 that Twitter trends could be detected before Twitter's own algorithm in 79% of cases — an average of 1.43 hours earlier — by monitoring velocity patterns instead of waiting for volume thresholds to trigger. The core insight hasn't changed: you're not looking for what's already big, you're looking for what's growing fast.

## What "Early" Actually Means

Early trend detection isn't about scraping more data. It's about measuring the right thing at the right time window. Three signals matter:

**Velocity over volume.** How fast are mentions accumulating, not how many total? A topic going from 50 mentions to 500 in 15 minutes is a stronger early signal than a topic with 10,000 steady daily mentions.

**Source diversity.** Are the mentions coming from a handful of accounts or spreading across unrelated ones? Twitter's own algorithm weights diverse participation — a spike from a coordinated group looks different from organic spread.

**Engagement acceleration.** Early retweets and replies from accounts with real follower counts amplify a topic's reach exponentially. Twitter's scoring uses logarithmic engagement scaling: `Score = weight × log2(1 + engagement_count)`, which means the first wave of engagement is disproportionately valuable for a topic's trajectory.

## The Two-Layer Detection Strategy

In practice, early detection works as a two-layer approach: monitoring velocity on specific topics you care about, and confirming against what's actually gone mainstream.

| Layer | Purpose | Endpoint |
|---|---|---|
| Filter Rules (streaming) | Catch velocity spikes early, before topics trend | `POST /v1/twitter/filter-rules` |
| Trends API | Confirm a topic has broken through to mainstream | `GET /v1/twitter/trends/place/{woeid}` |

The Trends API tells you what's already trending. The Filter Rules layer is where early detection actually happens.

## Step 1: Validate Your Query Syntax

Before creating a monitoring rule, run your query through the validate endpoint. Syntax errors in filter rules are a common source of wasted credits and missed signals.

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/filter-rules/validate" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "#AI -is:retweet min_faves:50"}'
```

The [filter rules documentation](https://scrapebadger.com/docs/twitter-streams/filter-rules) covers the full query syntax. Key operators for trend detection:

```
bitcoin OR ethereum              # Track multiple keywords simultaneously
#AI -is:retweet                  # Original tweets only — filters noise
"breaking news" min_faves:100    # High-engagement tweets only
from:elonmusk lang:en            # Specific account in a specific language
```

The `-is:retweet` operator matters more than most people realize. Retweets amplify existing content — they don't represent new conversation emerging. Filtering them out gives you a cleaner picture of where original discussion is actually originating.

## Step 2: Create a Filter Rule with the Right Polling Interval

This is where the polling tier selection determines how early you actually detect something.

| Tier | Poll Interval | Credits/Rule/Day |
|---|---|---|
| <span style="color: #2D6A4F; font-weight: bold;">Turbo</span> | Every 0.5 seconds | 30,000 |
| <span style="color: #2D6A4F; font-weight: bold;">Fast</span> | Every 5 seconds | 10,000 |
| <span style="color: #2D6A4F; font-weight: bold;">Standard</span> | Every 1 minute | 1,500 |
| <span style="color: #2D6A4F; font-weight: bold;">Relaxed</span> | Every 10 minutes | 500 |
| <span style="color: #2D6A4F; font-weight: bold;">Daily</span> | Every 24 hours | 100 |

For genuine early detection, Standard (1 minute) is the practical floor. Turbo and Fast are appropriate for high-stakes monitoring — financial signals, PR crisis detection, anything where a 30-second head start matters. For most keyword trend research, Standard gives you actionable lead time without burning through credits.

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/filter-rules" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "#AI -is:retweet min_faves:50",
    "tag": "ai-trend-monitor",
    "interval": "standard"
  }'
```

You can run up to 50 rules per API key. In practice, grouping related keywords into a single rule using `OR` operators is more efficient than creating one rule per keyword.

## Step 3: Connect via WebSocket for Real-Time Push Delivery

Polling the filter rules endpoint on your end adds unnecessary latency. The cleaner approach is to open a WebSocket connection and have matching tweets pushed to you as they're detected.

```python
import asyncio
import json
import websockets

async def stream_trends():
    uri = "wss://[your-domain]/v1/twitter/stream?api_key=YOUR_API_KEY"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "new_tweet":
                print(f"Rule: {data['rule_tag']}")
                print(f"@{data['author_username']}: {data['tweet_text']}")
                print(f"Detected in: {data['latency_ms']}ms")

asyncio.run(stream_trends())
```

The `latency_ms` field in each payload shows how quickly the tweet was detected after posting. In practice, this is typically under 2 seconds on the Fast tier.

Full WebSocket documentation: [scrapebadger.com/docs/twitter-streams/websocket](https://scrapebadger.com/docs/twitter-streams/websocket)

When a tweet arrives, the payload looks like this:

```json
{
  "type": "new_tweet",
  "source": "filter_rule",
  "rule_id": "rule-456",
  "rule_tag": "ai-trend-monitor",
  "tweet_id": "1234567890123456789",
  "author_username": "techcrunch",
  "tweet_text": "New AI model drops...",
  "tweet_type": "original",
  "latency_ms": 1200,
  "detected_at": "2026-03-04T12:00:00Z"
}
```

## Step 4: Confirm Against the Trends API

Once your pipeline flags a velocity spike, cross-reference it against the [Trends API](https://scrapebadger.com/docs/twitter/trends) to see whether the topic has broken into mainstream trending:

```bash
# Check global trends
curl "https://scrapebadger.com/v1/twitter/trends/place/1" \
  -H "x-api-key: YOUR_API_KEY"

# Check US-specific trends
curl "https://scrapebadger.com/v1/twitter/trends/place/23424977" \
  -H "x-api-key: YOUR_API_KEY"
```

Common WOEIDs for reference:

| WOEID | Location |
|---|---|
| `1` | Worldwide |
| `23424977` | United States |
| `23424975` | United Kingdom |
| `2459115` | New York |
| `2442047` | Los Angeles |

If your filter rule is flagging velocity but the topic isn't on the Trends API yet, that's the window you care about. That gap — between early velocity signal and mainstream trending — is where you can act.

## Building a Velocity Counter

The WebSocket stream gives you raw tweet events. To turn that into a velocity signal, you need to count events per time window and alert when the rate changes.

```python
import asyncio
import json
import time
import websockets
from collections import defaultdict, deque

# Sliding window: track tweet timestamps per rule tag
windows = defaultdict(deque)
WINDOW_SECONDS = 300  # 5-minute window
ALERT_THRESHOLD = 50  # tweets in window triggers alert

async def stream_with_velocity():
    uri = "wss://[your-domain]/v1/twitter/stream?api_key=YOUR_API_KEY"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] != "new_tweet":
                continue

            tag = data.get("rule_tag", "unknown")
            now = time.time()

            # Add current timestamp to window
            windows[tag].append(now)

            # Remove timestamps outside the window
            while windows[tag] and windows[tag][0] < now - WINDOW_SECONDS:
                windows[tag].popleft()

            count = len(windows[tag])

            # Alert on threshold breach
            if count >= ALERT_THRESHOLD:
                print(f"[ALERT] '{tag}' — {count} tweets in {WINDOW_SECONDS}s")

asyncio.run(stream_with_velocity())
```

This is the simplest version of velocity monitoring. In production, you'd want to persist these counts (Redis is the obvious choice), add per-rule baselines so alerts are relative to normal volume, and route alerts to Slack or a webhook.

For a more complete monitoring pipeline, the [How to Build a Real-Time Twitter Monitoring Pipeline](https://scrapebadger.com/blog/how_to_build_a_real-time_twitter_monitoring_pipeli) guide covers the deduplication and storage patterns in detail.

## Noise Filtering: Where Most Pipelines Fall Down

A velocity spike in your pipeline isn't automatically signal. Coordinated campaigns, bot activity, and retweet amplification can all produce false positives. A few filters that help:

- **Require original tweets** with `-is:retweet` in your query. Retweet storms look like trends but represent existing content spreading, not new conversation.
- **Set minimum engagement thresholds** — `min_faves:10` or `min_replies:5` filters out low-quality or automated posts.
- **Track source diversity** in your pipeline. If 90% of velocity is coming from accounts created in the same month, treat that as suspicious.
- **Use language filters** (`lang:en`) to avoid geographic noise inflating counts for topics irrelevant to your target market.

These aren't set-and-forget. After two weeks of monitoring, audit your false positive rate and tighten or loosen thresholds accordingly.

## When to Use Which Approach

| Use Case | Recommended Tier | Query Pattern |
|---|---|---|
| Brand PR crisis monitoring | Fast or Turbo | `"BrandName" -is:retweet` |
| Industry trend research | Standard | `keyword1 OR keyword2 -is:retweet` |
| High-engagement content sourcing | Standard | `keyword min_faves:100` |
| Competitor product launches | Standard or Fast | `from:competitor OR "product name"` |
| Market-wide signal monitoring | Relaxed | `broad_keyword lang:en` |

The Standard tier handles most use cases without breaking your credit budget. Reserve Fast and Turbo for specific high-stakes signals where lead time is the actual business requirement.

If you're building trend detection as part of a broader competitor monitoring workflow, the [Twitter Monitoring vs Twitter Scraping: What's the Difference?](https://scrapebadger.com/blog/twitter_monitoring_vs_twitter_scraping_what's_the) post is worth reading for context on how to structure the overall approach.

---

## FAQ

**What's the difference between the Trends API and filter rules for trend detection?**

The Trends API ([`GET /v1/twitter/trends/place/{woeid}`](https://scrapebadger.com/docs/twitter/trends)) shows what's already trending — topics that have already hit mainstream volume thresholds. Filter rules are proactive: they monitor for velocity on specific queries *before* a topic appears on any trending list. Early detection means using filter rules; the Trends API is for confirmation that something has broken through.

**How early can I realistically detect a trend before Twitter's own algorithm flags it?**

MIT research showed an average of 1.43 hours earlier detection with velocity-based methods (at 95% accuracy). In practice, with a Standard (1-minute) polling interval, you're getting signal well before the official trending list. The Fast (5-second) tier narrows that gap further. The actual lead time depends heavily on how niche or broad the topic is — niche topics trending within a specific community can be detected significantly earlier than news-driven spikes.

**How many filter rules should I run simultaneously?**

ScrapeBadger supports up to 50 rules per API key. In practice, grouping related keywords with `OR` operators into fewer rules is more efficient than creating one per keyword. For example, `#OpenAI OR #GPT OR "ChatGPT" -is:retweet` as a single rule is cleaner than three separate rules and uses credits more efficiently.

**How do I avoid false positives from bot activity or coordinated posting?**

Three approaches work together: filter to original content with `-is:retweet`, require minimum engagement (`min_faves:10`), and monitor source diversity in your pipeline. If a velocity spike is concentrated among accounts with similar creation dates or follower patterns, treat it as a false positive. Auditing your pipeline's false positive rate every few weeks and adjusting thresholds based on actual results is more reliable than trying to tune parameters upfront.

**What's the right polling interval for most use cases?**

Standard (1-minute polling) is the practical default for most trend monitoring workflows. It provides real-time enough detection for content strategy, brand monitoring, and market research without the credit cost of Fast or Turbo tiers. Reserve the faster tiers for high-stakes use cases — financial signal monitoring, PR crisis detection, or anything where minutes genuinely matter to your response time.

**Can I use WebSocket streaming and filter rules together?**

Yes, and this is the recommended architecture. Create filter rules via the REST API (`POST /v1/twitter/filter-rules`) to define what you're monitoring, then connect via WebSocket to receive matching tweets pushed in real time without polling. The WebSocket connection handles up to 5 concurrent connections per API key. See the [WebSocket documentation](https://scrapebadger.com/docs/twitter-streams/websocket) for connection details and event handling.

**Is detecting trends on Twitter the same as monitoring keywords?**

They overlap but aren't the same. Keyword monitoring tracks mentions of specific terms you define. Trend detection is specifically about measuring the *rate of change* in those mentions — velocity, not volume. A keyword monitor tells you how many mentions you're getting. A trend detector tells you whether that number is accelerating in a way that signals something is about to break through. The pipeline described here does both: keyword monitoring via filter rules, trend detection via the velocity counter layer built on top.