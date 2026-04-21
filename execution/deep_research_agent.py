"""
deep_research_agent.py

Deep Research Agent for ScrapeBadger blog pipeline.
Runs a sequential multi-tool research pipeline:

  1. Tavily API    → broad web search (10+ sources)
  2. Perplexity   → deep synthesized research report
  3. Exa AI       → semantic search for tech articles & discussions
  4. Firecrawl    → full content scraping of top URLs found

Output: .tmp/research_[safe_topic].txt — loaded by generate_blog_claude.py

Usage:
    python3 execution/deep_research_agent.py
"""

import os
import re
import time
import requests

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_FILE    = os.path.join(BASE_DIR, "anthropic_key.txt")
OUTPUT_DIR   = os.path.join(BASE_DIR, ".tmp")

# ── Research Inputs ───────────────────────────────────────────────────────────
TOPIC           = "How to Track Competitors on Twitter Without the Official API"
PRIMARY_KEYWORD = "tracking competitors twitter"
NUM_RESULTS     = 8   # number of search results per tool


# ── Key Loader ────────────────────────────────────────────────────────────────
def load_keys() -> dict:
    """Read KEY=VALUE pairs from anthropic_key.txt."""
    keys = {}
    with open(KEYS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys

# ── Input Loader ──────────────────────────────────────────────────────────────
def load_inputs():
    """Load inputs from .tmp/blog_inputs.json if available."""
    global TOPIC, PRIMARY_KEYWORD
    override_file = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")
    if os.path.exists(override_file):
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
                TOPIC = data.get("topic", TOPIC)
                PRIMARY_KEYWORD = data.get("primary_keyword", PRIMARY_KEYWORD)
                print(f"  📋 Loaded Topic from Telegram Override: {TOPIC}")
        except Exception as e:
            print(f"  ⚠️ Could not read Telegram override ({e})")


# ── STEP 1: Tavily ────────────────────────────────────────────────────────────
def run_tavily(api_key: str, topic: str) -> str:
    print("\n[1/4] Tavily: broad web search...")
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": topic,
        "search_depth": "advanced",
        "max_results": NUM_RESULTS,
        "include_raw_content": False,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    lines = [f"=== TAVILY SEARCH: {topic} ===\n"]
    for r in data.get("results", []):
        lines.append(f"SOURCE: {r.get('url', '')}")
        lines.append(f"TITLE: {r.get('title', '')}")
        lines.append(r.get("content", ""))
        lines.append("")

    result = "\n".join(lines)
    print(f"  ✅ Got {len(data.get('results', []))} results")
    return result


# ── STEP 2: Perplexity ────────────────────────────────────────────────────────
def run_perplexity(api_key: str, topic: str) -> str:
    print("\n[2/4] Perplexity: deep synthesized research...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Do thorough research on: {topic}\n\n"
                    f"Focus on: practical approaches, technical details, tools, "
                    f"current market situation (2025-2026), common problems teams face, "
                    f"and real-world solutions. Include specific data points where available."
                ),
            }
        ],
    }
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    result = f"=== PERPLEXITY DEEP RESEARCH: {topic} ===\n\n{content}"
    print(f"  ✅ Got {len(content):,} chars of research")
    return result


# ── STEP 3: Exa AI ────────────────────────────────────────────────────────────
def run_exa(api_key: str, topic: str) -> str:
    print("\n[3/4] Exa AI: semantic search for tech content...")
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "query": topic,
        "numResults": NUM_RESULTS,
        "useAutoprompt": True,
        "type": "neural",
        "contents": {
            "text": {"maxCharacters": 2000},
        },
    }
    resp = requests.post(
        "https://api.exa.ai/search",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    lines = [f"=== EXA AI SEMANTIC SEARCH: {topic} ===\n"]
    for r in data.get("results", []):
        lines.append(f"SOURCE: {r.get('url', '')}")
        lines.append(f"TITLE: {r.get('title', '')}")
        text = r.get("text", "") or ""
        lines.append(text[:2000])
        lines.append("")

    result = "\n".join(lines)
    print(f"  ✅ Got {len(data.get('results', []))} results")
    return result


# ── STEP 4: Firecrawl ─────────────────────────────────────────────────────────
def run_firecrawl(api_key: str, urls: list[str]) -> str:
    """Scrape the top URLs discovered by previous steps."""
    print(f"\n[4/4] Firecrawl: deep scraping {len(urls)} top URLs...")
    if not urls:
        return "=== FIRECRAWL: No URLs to scrape ===\n"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    lines = [f"=== FIRECRAWL DEEP SCRAPE ===\n"]

    for url in urls[:3]:  # limit to top 3 to control cost
        try:
            payload = {"url": url, "formats": ["markdown"]}
            resp = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("data", {}).get("markdown", "")[:3000]
            lines.append(f"SOURCE: {url}")
            lines.append(content)
            lines.append("")
            print(f"  ✅ Scraped {url[:60]}...")
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Firecrawl error for {url}: {e}")

    return "\n".join(lines)


# ── URL Extractor ─────────────────────────────────────────────────────────────
def extract_urls(text: str, limit: int = 5) -> list[str]:
    """Pull URLs from research text for Firecrawl to deep-scrape."""
    urls = re.findall(r'https?://[^\s\'"<>]+', text)
    # Filter out social media, ads, etc.
    filtered = [u for u in urls if not any(x in u for x in
                ["twitter.com", "facebook.com", "instagram.com",
                 "google.com/search", "youtube.com", "amazon.com"])]
    # Deduplicate preserving order
    seen = set()
    result = []
    for u in filtered:
        if u not in seen:
            seen.add(u)
            result.append(u)
        if len(result) >= limit:
            break
    return result


# ── Save Output ───────────────────────────────────────────────────────────────
def save_research(topic: str, sections: list[str]) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", topic.lower())[:50]
    path = os.path.join(OUTPUT_DIR, f"research_{safe}.txt")
    full = "\n\n" + ("=" * 60) + "\n\n".join(sections)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"DEEP RESEARCH REPORT\nTopic: {topic}\n\n")
        f.write(full)
    print(f"\n📄 Research saved: {path}")
    return path


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    load_inputs()
    print(f"🔍 Deep Research Agent\nTopic: {TOPIC}\n")
    keys = load_keys()

    sections = []
    tavily_result = ""
    exa_result = ""

    # Step 1 — Tavily
    try:
        tavily_result = run_tavily(keys["TAVILY_API_KEY"], TOPIC)
        sections.append(tavily_result)
    except Exception as e:
        print(f"  ⚠️  Tavily failed: {e}")
    time.sleep(1)

    # Step 2 — Perplexity
    try:
        perplexity_result = run_perplexity(keys["PERPLEXITY_API_KEY"], TOPIC)
        sections.append(perplexity_result)
    except Exception as e:
        print(f"  ⚠️  Perplexity failed: {e}")
    time.sleep(1)

    # Step 3 — Exa
    try:
        exa_result = run_exa(keys["EXA_API_KEY"], TOPIC)
        sections.append(exa_result)
    except Exception as e:
        print(f"  ⚠️  Exa failed: {e}")
    time.sleep(1)

    # Step 4 — Firecrawl (uses URLs from Tavily + Exa results)
    try:
        top_urls = extract_urls(tavily_result + exa_result)
        firecrawl_result = run_firecrawl(keys["FIRECRAWL_API_KEY"], top_urls)
        sections.append(firecrawl_result)
    except Exception as e:
        print(f"  ⚠️  Firecrawl failed: {e}")

    # Save combined report
    output_path = save_research(TOPIC, sections)
    print(f"\n✅ Done! Research report ready at:\n   {output_path}")
    print("\nNext step: run generate_blog_claude.py to write the blog.")


if __name__ == "__main__":
    main()
