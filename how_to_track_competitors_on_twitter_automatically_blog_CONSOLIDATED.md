# Blog Post Package

## SEO Metadata
Primary Keyword: track competitors on Twitter
Meta Title: How to Track Competitors on Twitter Automatically
Meta Description: Learn how to track competitors on Twitter automatically using Stream Monitors, webhooks, and engagement APIs. Stop missing key signals and start acting on real data.


---

## LinkedIn Post
Most teams track competitors on Twitter manually. Someone searches a name, skims results, gets busy, and stops.

Three weeks later, a competitor launched a new product and got 800 retweets. Nobody saw it.

The problem is not effort. It is the absence of automation.

Here is what a reliable competitor tracking system actually requires:

- Real-time stream monitors that capture every tweet, reply, and retweet the moment it is posted
- Follower velocity tracking, not vanity follower counts, to spot launches before announcements go public
- Engagement analysis on high-performing competitor tweets to understand why content works, not just that it did

Teams monitoring properly see competitor moves 10 to 15 days ahead of when quarterly reports would surface them.

The infrastructure to do this is simpler than most assume. A stream monitor, a webhook endpoint, a weekly profile snapshot job, and a Slack alert on engagement thresholds. That is the core of it.

Read the full guide at scrapebadger.com

What signals are you currently missing because your competitor tracking is still manual? Drop your answer below.

---

## Twitter Thread
Manual competitor tracking on Twitter is how you miss product launches in real time.

- Stream monitors catch every tweet the moment it posts
- Follower velocity reveals launches before announcements
- Engagement data shows why content works, not just reach

Read the full guide: scrapebadger.com

---

## Blog Cover Image
![Cover Image](how_to_track_competitors_on_twitter_automatically_blog_cover.png)

---

# How to Track Competitors on Twitter Automatically

Most teams track competitors on Twitter the same way: manually. Someone searches a product name every few days, skims the results, maybe screenshots something useful. Then they get busy and stop. Three weeks later, a competitor launched a new pricing page and got 800 retweets, and nobody on your team saw it.

The fix isn't checking more often. It's automating the collection entirely so you stop missing signals that actually change decisions.

This guide covers what's worth tracking, how to set up an automated pipeline using the [ScrapeBadger Stream Monitors API](https://scrapebadger.com/docs/twitter-streams/monitors), and how to structure everything so the output is actually useful rather than a pile of raw data nobody reads.

## What You're Actually Trying to Learn

Before setting anything up, be specific about what you want. "Track competitors" is not a goal. Here are the signals that actually matter:

**Content strategy signals** — what they post, how often, which formats drive engagement, what they're amplifying. Posting patterns reveal resource allocation. A competitor suddenly pushing video-heavy threads on a topic you've been ignoring is a signal worth acting on.

**Audience growth** — follower velocity, who follows them recently, whether they're gaining verified or notable accounts. A sudden spike in verified followers usually means a meaningful press hit or partnership — before any announcement goes out.

**Strategic moves** — product launches, pricing changes, partnership announcements. These almost always surface on Twitter before formal press releases. If you're monitoring properly, you see competitor moves <span style="color: #2D6A4F; font-weight: bold;">10–15 days</span> ahead of when quarterly reports would catch them.

**Reaction data** — replies, quote tweets, and who's retweeting them. This tells you how their audience actually feels about something, not just how many people saw it.

## The Core Approach: Stream Monitors

The most reliable way to track competitor activity automatically is with Stream Monitors. Instead of polling for competitor tweets on a schedule, a monitor watches specific accounts in real time and delivers every tweet, reply, retweet, and quote tweet to a webhook endpoint the moment it's posted.

The ScrapeBadger [Stream Monitors API](https://scrapebadger.com/docs/twitter-streams/monitors) handles this with a straightforward setup: create a monitor, point it at competitor accounts, configure a webhook, and start receiving structured payloads.

### Step 1: Create a Monitor

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/stream/monitors" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "accounts": ["competitor_one", "competitor_two", "competitor_three"],
    "label": "competitors-q3"
  }'
```

You can track up to <span style="color: #2D6A4F; font-weight: bold;">100 accounts</span> per monitor. Keep related competitors grouped into labelled monitors — one for direct competitors, one for adjacent players you're watching more loosely.

### Step 2: Set Up Your Webhook

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/stream/webhooks" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "monitor_id": "YOUR_MONITOR_ID",
    "url": "https://your-server.com/webhooks/twitter"
  }'
```

Verify it's working before relying on it:

```bash
curl -X POST "https://scrapebadger.com/v1/twitter/stream/webhooks/test" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"webhook_id": "YOUR_WEBHOOK_ID"}'
```

If you don't get a test payload within a few seconds, something is wrong with your endpoint before you've wasted any credits on real monitoring.

### ⚠️ Shadow Account Warning — Check This First

Before adding any account to a monitor, verify it isn't shadow-banned. A shadow-banned account returns no results — your monitor runs, credits tick, and you receive nothing. Check by visiting:

```
https://x.com/search?q=from%3AUSERNAME&src=typed_query&f=live
```

If an account actively posts but the search returns empty, it's shadow-banned. Don't add it to a monitor until this is resolved.

## Billing Model: What It Actually Costs

Stream monitors are billed per account per day, with volume discounts as you add more accounts.

| Tier | Accounts | Credits per Account per Day |
|------|----------|-----------------------------|
| Starter | 1–10 | 1,667 |
| Growth | 11–50 | 1,333 |
| Scale | 51–100 | 1,000 |
| Enterprise | 101+ | 833 |

In practice, most teams tracking <span style="color: #2D6A4F; font-weight: bold;">5–15 competitors</span> sit in the Starter or Growth tier. The per-day cost drops significantly as you add more accounts, so consolidating your monitoring into fewer, larger monitors is more economical than running many small ones.

## Pulling Competitor Profile Snapshots

Stream monitors handle the real-time feed. But before you start monitoring, you want a baseline: follower count, verification status, account age, bio keywords. This is your starting point for measuring change over time.

Use the [Twitter Users API](https://scrapebadger.com/docs/twitter/users) for this:

```python
import httpx

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://scrapebadger.com/v1/twitter"

def get_competitor_profile(username: str) -> dict:
    """Fetch full profile data for a competitor account."""
    response = httpx.get(
        f"{BASE_URL}/users/{username}/by_username",
        headers={"x-api-key": API_KEY}
    )
    return response.json()

def get_recent_tweets(username: str, max_items: int = 50) -> list:
    """Pull the competitor's most recent tweets."""
    response = httpx.get(
        f"{BASE_URL}/users/{username}/latest_tweets",
        headers={"x-api-key": API_KEY},
        params={"max_items": max_items}
    )
    return response.json().get("data", [])
```

Run this weekly per competitor. Store the follower count and engagement averages in a simple table. After a month, you'll have a trend line — not just a snapshot.

## Analyzing Engagement on Specific Tweets

When a competitor tweet performs unusually well, you want to understand why. The [Tweet engagement endpoints](https://scrapebadger.com/docs/twitter/tweets) let you pull full engagement data after the fact:

```python
def analyze_tweet(tweet_id: str) -> dict:
    """Get full engagement breakdown for a specific tweet."""
    endpoints = {
        "detail": f"{BASE_URL}/tweets/tweet/{tweet_id}",
        "retweeters": f"{BASE_URL}/tweets/tweet/{tweet_id}/retweeters",
        "replies": f"{BASE_URL}/tweets/tweet/{tweet_id}/replies",
        "quotes": f"{BASE_URL}/tweets/tweet/{tweet_id}/quotes",
    }
    results = {}
    for key, url in endpoints.items():
        r = httpx.get(url, headers={"x-api-key": API_KEY})
        results[key] = r.json()
    return results
```

The replies endpoint is particularly useful — it shows you unfiltered audience reaction. Quote tweets tell you how content spreads and what commentary gets added. Both are hard to interpret from engagement counts alone.

## Searching for Competitor Mentions

Real-time monitors track what competitors post. The [advanced search endpoint](https://scrapebadger.com/docs/twitter/tweets) tracks what others say *about* them.

```bash
# What others say about a competitor
GET /v1/twitter/tweets/advanced_search?query="CompetitorBrand" -from:competitorhandle&type=Latest

# Their original content only (no retweets)
GET /v1/twitter/tweets/advanced_search?query=from:competitorhandle -is:retweet&type=Latest

# High-engagement campaign content
GET /v1/twitter/tweets/advanced_search?query=%23CompetitorCampaign min_faves:50&type=Top
```

The same shadow-ban caveat applies here. Using `from:username` on a shadow-banned account returns empty results. Always verify the account first.

## Tracking Competitor Audience Movement

Follower velocity is one of the most underused signals. A competitor gaining <span style="color: #2D6A4F; font-weight: bold;">5,000 followers</span> in a week on a niche topic is worth investigating — it often precedes a launch or campaign that hasn't been announced yet.

The [follower endpoints](https://scrapebadger.com/docs/twitter/users) give you everything you need:

| Endpoint | What It Tells You |
|----------|-------------------|
| `/v1/twitter/users/{username}/latest_followers` | Who followed them most recently |
| `/v1/twitter/users/{username}/verified_followers` | Notable or verified accounts following them |
| `/v1/twitter/users/{username}/latest_following` | Accounts they've recently started following |

The `latest_following` endpoint is one people forget about. When a competitor starts following a cluster of accounts in a new vertical, it's often a signal they're moving into adjacent market territory.

## Putting It Together: A Minimal Tracking Stack

You don't need a complex system to make this useful. Here's the minimal version that actually holds up over time:

| Component | Approach |
|-----------|----------|
| Real-time feed | Stream Monitor with webhook to a simple endpoint |
| Weekly profile snapshots | Cron job calling `/by_username` and writing to SQLite |
| Engagement deep-dives | Manual trigger on high-performing tweet IDs |
| Mention tracking | Scheduled advanced search job, daily |
| Alerts | Slack webhook for any tweet above engagement threshold |

The webhook endpoint can be as simple as a Flask route that writes incoming payloads to a database and checks whether the engagement metrics cross a threshold before firing a Slack alert.

For a more detailed look at how to [scrape Twitter user timelines automatically](https://scrapebadger.com/blog/how_to_scrape_twitter_user_timelines_automatically), including pagination handling and normalization patterns, that's covered separately.

## What's Not Worth Tracking (Signal vs. Noise)

A few honest notes on what to deprioritize:

**Raw tweet volume** doesn't tell you much. A competitor posting 10 times a day isn't inherently significant. Posting frequency matters when it correlates with a specific campaign or product push.

**Follower count** as a vanity metric is almost useless. Follower *velocity* is what matters — rate of change, not absolute number.

**Broad keyword searches** on generic terms will drown you in irrelevant content fast. Start narrow: exact brand names, specific product names, `from:handle` queries. Expand only when you know what signal you're looking for.

The [Twitter Monitoring vs Twitter Scraping guide](https://scrapebadger.com/blog/twitter_monitoring_vs_twitter_scraping_whats_the_d) covers this distinction in more depth if you're deciding which approach fits your use case.

## FAQ

**How often should I monitor competitor accounts?**
Real-time monitoring via Stream Monitors is the most reliable approach — it catches everything without polling delays. If real-time isn't necessary, a daily cron job pulling recent tweets is a reasonable fallback for most use cases. Match frequency to urgency: product launches warrant real-time; general content strategy analysis is fine daily.

**Can I track competitor accounts I don't follow?**
Yes. All the endpoints discussed here work on any public Twitter account, regardless of whether you follow them. The Stream Monitor and user endpoints have no follow-requirement.

**What if a competitor account returns no results?**
The most common cause is shadow-banning. Check the account at `https://x.com/search?q=from%3AUSERNAME&src=typed_query&f=live` before concluding there's a technical problem. If the search returns no tweets for an actively posting account, the account is shadow-banned and the endpoints will return empty results until that's resolved.

**How many competitors can I track simultaneously?**
A single Stream Monitor supports up to 100 accounts. You can run multiple monitors if you need to track more, or segment by category (direct competitors, adjacent players, influencers in your space).

**What's the difference between Stream Monitors and scheduled search jobs?**
Monitors deliver tweets in real time as they're posted, with zero polling delay. Scheduled search jobs are better for pulling historical data or tracking mentions by keyword rather than by specific account. For competitor account tracking, monitors are the more reliable choice. For tracking what people say *about* a competitor, advanced search on a schedule works well.

**How do I avoid collecting noise I'll never look at?**
Set engagement thresholds before you write anything to storage. Anything under 5 likes from a non-verified account usually isn't actionable for competitive tracking. Also add negative keywords to your search queries upfront — `-giveaway -contest -is:retweet` cuts volume significantly without losing meaningful signal.

**Is tracking competitors on Twitter legal?**
All of this applies to public accounts and publicly visible tweets. Reviewing the platform's terms of service and any relevant laws in your jurisdiction before building a production system is always the right move.