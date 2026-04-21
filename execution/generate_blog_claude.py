"""
generate_blog_claude.py

Generates a ScrapeBadger blog post using Claude Sonnet via the Anthropic API.
- Loads the style guide from directives/scrapebadger_blog_style.md as the system prompt
- Loads ScrapeBadger blog examples from .tmp/examples/ as few-shot context
- Loads deep research report from .tmp/research_*.txt if available
- Accepts topic, primary keyword, secondary keywords, and word count as inputs
- Saves the result to twitter_competitor_tracking_blog.md
- Writes the result to Google Sheets (C2)

Usage:
    python3 execution/generate_blog_claude.py
"""

import os
import re
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE        = os.path.join(BASE_DIR, ".env")
STYLE_GUIDE     = os.path.join(BASE_DIR, "directives", "scrapebadger_blog_style.md")
EXAMPLES_DIR  = os.path.join(BASE_DIR, ".tmp", "examples")
RESEARCH_DIR  = os.path.join(BASE_DIR, ".tmp")
DOCS_CONTEXT  = os.path.join(BASE_DIR, ".tmp", "docs_context.txt")
SEO_FEEDBACK  = os.path.join(BASE_DIR, ".tmp", "seo_feedback.txt")
ANTI_PATTERNS = os.path.join(BASE_DIR, "directives", "tone_anti_patterns.md")
OUTPUT_MD       = None # Will be set dynamically by get_output_path()
REPAIR_FEEDBACK = os.path.join(BASE_DIR, ".tmp", "repair_feedback.txt")
CREDENTIALS     = os.path.join(BASE_DIR, "credentials.json")

# ── Google Sheets ─────────────────────────────────────────────────────────────
SHEET_ID        = "1slKBmFxgflToccBLxOTcSDlE2bi_x5pHDCeukcn54p0"
SCOPES          = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Blog Inputs (loaded dynamically from Google Sheet) ────────────────────────
# Defaults used only if the Sheet row is empty
_DEFAULT_TOPIC              = "How to Track Competitors on Twitter (X) Without the Official API"
_DEFAULT_PRIMARY_KEYWORD    = "tracking competitors twitter"
_DEFAULT_SECONDARY_KEYWORDS = "twitter scraper, competitor monitoring, keyword tracking, no api twitter"
_DEFAULT_WORD_COUNT         = 2000

# Will be populated by load_blog_inputs_from_sheet()
TOPIC              = _DEFAULT_TOPIC
PRIMARY_KEYWORD    = _DEFAULT_PRIMARY_KEYWORD
SECONDARY_KEYWORDS = _DEFAULT_SECONDARY_KEYWORDS
WORD_COUNT         = _DEFAULT_WORD_COUNT
ROW_IDX            = 2 # Default row to write back to

# ── Prompt Construction ──────────────────────────────────────────────────────
def build_prompt(style_guide: str, examples: str, research: str, docs: str, seo_feedback: str, repair_feedback: str) -> str:
    prompt = f"""You are the master content writer for ScrapeBadger.
Your goal is to write a high-converting, deeply technical, yet accessible blog post about: "{TOPIC}"

### CRITICAL STRUCTURAL CONSISTENCY
You MUST follow the EXACT structural pattern seen in the provided EXAMPLES. 
1. The post MUST start with an H1 title (no Markdown code block wrappers).
2. Every major section must be an H2, followed by dense, informative paragraphs (no fluff).
3. Use Markdown tables for any product/tool comparisons. Keep tables CLEAN (plain borders only, NO background colors, and NO colored text/spans inside tables).
4. Use <span style="color: #2D6A4F; font-weight: bold;">green</span> highlights for data mentions and statuses OUTSIDE of tables. DO NOT use highlighting for "Tier" names or labels in tables (e.g. keep Tier, Standard, Turbo as plain text). NEVER use red or other colors.
5. You MUST include a ## FAQ section at the end with at least 5 relevant questions and answers.
6. DO NOT "grybauti" ( Lithuanian for "getting lost" or "deviating"). Stick to the technical facts and the ScrapeBadger voice.

### STYLE GUIDE
{style_guide}

### FEW-SHOT EXAMPLES (Follow this exact structural skeleton)
{examples}

### MANDATORY INSTRUCTION
Your output MUST look and feel exactly like the examples above. If an example uses a table for comparisons, you MUST use a table. If an example has a specific density of technical details, you MUST match it.

### RESEARCH
{research}

### TECHNICAL DOCUMENTATION
{docs}

### SEO FEEDBACK (if applicable)
{seo_feedback}

### REPAIR FEEDBACK (if applicable)
{repair_feedback}

### BLOG POST DETAILS
Topic: {TOPIC}
Primary Keyword: {PRIMARY_KEYWORD}
Secondary Keywords: {SECONDARY_KEYWORDS}
Target Word Count: Around {WORD_COUNT} words (this is a RECOMMENDATION, not a hard limit). The text can be longer or shorter depending on what the topic requires. Quality and completeness are the priority — never cut content short to hit a number. Cover the topic fully, even if that means going over or under the target.

Output only the blog post text. No meta-commentary. Use rich Markdown formatting (e.g. ## for headers, ** for bold) and triple backticks (```) for Inline Code Examples.
"""
    return prompt

# ── Model ─────────────────────────────────────────────────────────────────────
# This acts as a fallback if CLAUDE_MODEL isn't found in anthropic_key.txt
MODEL_FALLBACK = "claude-sonnet-4-6"


def load_blog_inputs_from_sheet():
    """Read Topic, Primary KW, Secondary KWs, and Word Count from Google Sheet row 2.
    Sheet column layout (after restructuring):
      A = Topic
      B = Primary Keyword
      C = Secondary Keywords
      D = Word Count
      E = Status
      F = Generated Blog  (written back by write_to_sheet)
    """
    global TOPIC, PRIMARY_KEYWORD, SECONDARY_KEYWORDS, WORD_COUNT

    # 1. Check for Telegram Override FIRST
    override_file = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")
    if os.path.exists(override_file):
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
                TOPIC              = data.get("topic", _DEFAULT_TOPIC)
                PRIMARY_KEYWORD    = data.get("primary_keyword", _DEFAULT_PRIMARY_KEYWORD)
                SECONDARY_KEYWORDS = data.get("secondary_keywords", _DEFAULT_SECONDARY_KEYWORDS)
                WORD_COUNT         = int(data.get("word_count", _DEFAULT_WORD_COUNT))
                ROW_IDX            = int(data.get("row_idx", 2))
                print(f"  📋 Loaded inputs from Telegram Override:")
                print(f"     Topic:      {TOPIC}")
                print(f"     Primary KW: {PRIMARY_KEYWORD}")
                print(f"     Secondary:  {SECONDARY_KEYWORDS}")
                print(f"     Word Count: {WORD_COUNT}")
                print(f"     Row Index:  {ROW_IDX}")
                return # Exit early, don't read from Sheets
        except Exception as e:
            print(f"  ⚠️ Could not read Telegram override ({e})")

    # 2. Fallback to Google Sheets: Find the first pending row
    try:
        creds  = Credentials.from_service_account_file(CREDENTIALS, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(SHEET_ID).sheet1
        
        # Get all records
        records = sheet.get_all_records()
        target_row_data = None
        target_row_idx = 2
        
        for i, r in enumerate(records):
            # Dynamic header detection for status
            status_val = ""
            for key in r.keys():
                if any(x in key.lower() for x in ["status", "process", "būsena"]):
                    status_val = str(r[key]).strip().lower()
                    break
            
            if status_val not in ['done', 'completed', 'finished', '✅ completed']:
                target_row_data = r
                target_row_idx = i + 2
                break
        
        if target_row_data:
            # Helper for robust value extraction
            def get_val(names, default=""):
                for k in target_row_data.keys():
                    if any(n.lower() in k.lower() for n in names):
                        return target_row_data[k]
                return default

            TOPIC              = get_val(["topic", "tema"], _DEFAULT_TOPIC)
            PRIMARY_KEYWORD    = get_val(["primary keyword", "raktažodis"], _DEFAULT_PRIMARY_KEYWORD)
            SECONDARY_KEYWORDS = get_val(["secondary keywords"], "")
            wc_raw             = get_val(["word count", "žodžių skaičius"], str(_DEFAULT_WORD_COUNT))
            WORD_COUNT         = int(wc_raw) if str(wc_raw).isdigit() else _DEFAULT_WORD_COUNT
            ROW_IDX            = target_row_idx
        else:
            # Fallback
            ROW_IDX = 2

        print(f"  📋 Loaded inputs from Sheet (Row {ROW_IDX}):")
        print(f"     Topic:      {TOPIC}")
        print(f"     Primary KW: {PRIMARY_KEYWORD}")
        print(f"     Secondary:  {SECONDARY_KEYWORDS}")
        print(f"     Word Count: {WORD_COUNT}")
    except Exception as e:
        print(f"  ⚠️  Could not read inputs from Sheet ({e}) — using defaults")

def get_slug(text: str):
    """Generate a clean slug from text."""
    slug = text.lower().strip()
    slug = slug.replace(" ", "_").replace(":", "").replace("?", "").replace("'", "").replace("(","").replace(")","").replace("“","").replace("”","").replace("’","").replace("/","_")
    slug = re.sub(r'_+', '_', slug)
    if len(slug) > 50: slug = slug[:50]
    if slug.endswith("_"): slug = slug[:-1]
    return slug

def get_output_path():
    """Generate a clean filename from the topic."""
    fname_base = get_slug(TOPIC)
    return os.path.join(BASE_DIR, f"{fname_base}_blog.md")

def discover_internal_links() -> str:
    """Fetch real blog URLs from ScrapeBadger sitemap to ensure all links are valid."""
    import requests
    from bs4 import BeautifulSoup

    links = []
    try:
        print("  Fetching ScrapeBadger sitemap for internal links...")
        resp = requests.get("https://scrapebadger.com/sitemap.xml",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "xml")
        for url_node in soup.find_all("url"):
            loc = url_node.find("loc")
            if loc and "/blog/" in loc.text:
                url = loc.text.strip()
                # Extract readable title from slug
                slug = url.split("/blog/")[-1].rstrip("/")
                title = slug.replace("-", " ").title()
                links.append(f"- [{title}]({url})")
        print(f"  Found {len(links)} real blog URLs for internal linking")
    except Exception as e:
        print(f"  ⚠️ Could not fetch sitemap for internal links: {e}")
        return ""

    return "\n".join(links) if links else ""


def load_style_guide() -> str:
    with open(STYLE_GUIDE, "r") as f:
        return f.read()


def load_examples() -> str:
    """Load any .txt or .md example blog files from .tmp/ as few-shot context."""
    examples = []
    if not os.path.exists(EXAMPLES_DIR):
        return ""
    for fname in os.listdir(EXAMPLES_DIR):
        if fname.endswith((".md", ".txt")):
            fpath = os.path.join(EXAMPLES_DIR, fname)
            with open(fpath, "r") as f:
                content = f.read().strip()
            if content:
                examples.append(f"--- EXAMPLE: {fname} ---\n{content}\n")
    return "\n".join(examples)


def load_research() -> str:
    """Load the most recent research report from .tmp/research_*.txt if available."""
    if not os.path.exists(RESEARCH_DIR):
        return ""
    reports = sorted([
        os.path.join(RESEARCH_DIR, f)
        for f in os.listdir(RESEARCH_DIR)
        if f.startswith("research_") and f.endswith(".txt")
    ], key=os.path.getmtime, reverse=True)
    if not reports:
        return ""
    with open(reports[0], "r") as f:
        content = f.read().strip()
    print(f"  Loaded research: {os.path.basename(reports[0])} ({len(content):,} chars)")
    return content


def load_seo_feedback() -> str:
    """Load SEO feedback from the checker agent if a rewrite is needed."""
    if not os.path.exists(SEO_FEEDBACK):
        return ""
    with open(SEO_FEEDBACK, "r") as f:
        content = f.read().strip()
    print(f"  Loaded SEO feedback ({len(content):,} chars) — rewrite mode")
    return content


def load_anti_patterns() -> str:
    """Load the user's explicit anti-patterns to avoid."""
    if not os.path.exists(ANTI_PATTERNS):
        return ""
    with open(ANTI_PATTERNS, "r") as f:
        content = f.read().strip()
    return content


def load_docs_context() -> str:
    """Load ScrapeBadger API documentation context extracted by Docs Agent."""
    if not os.path.exists(DOCS_CONTEXT):
        return ""
    with open(DOCS_CONTEXT, "r") as f:
        content = f.read().strip()
    if content and "No specific ScrapeBadger technical documentation" not in content:
        print(f"  Loaded technical docs context ({len(content):,} chars)")
        return content
    return ""


def load_repair_feedback() -> str:
    """Load user repair feedback from Telegram if available."""
    if not os.path.exists(REPAIR_FEEDBACK):
        return ""
    with open(REPAIR_FEEDBACK, "r") as f:
        content = f.read().strip()
    print(f"  Loaded Repair Feedback ({len(content):,} chars) — refinement mode")
    return content


def build_user_message() -> str:
    examples = load_examples()
    research = load_research()
    docs_context = load_docs_context()
    seo_feedback = load_seo_feedback()
    anti_patterns = load_anti_patterns()
    repair_feedback = load_repair_feedback()

    few_shot = ""
    if examples:
        few_shot = (
            "CRITICAL WARNING: The examples below are primarily about Twitter. "
            "DO NOT assume the current article is about Twitter unless explicitly stated in the Topic! "
            "Use these examples ONLY for structuring your markdown, tables, and tone of voice. "
            "If the Topic is about e-commerce, generic web scraping, or Vinted, DO NOT mention Twitter.\n\n"
            "Here are examples of existing posts for structure/style reference:\n\n"
            + examples
            + "\n\n---\n\n"
        )

    research_section = ""
    if research:
        research_section = (
            "Here is deep research on the topic gathered from multiple sources. "
            "Use the facts, data points, and insights from this research to make the blog post accurate and authoritative:\n\n"
            + research
            + "\n\n---\n\n"
        )

    docs_section = ""
    if docs_context:
        docs_section = (
            "Here is the official API documentation and technical context for ScrapeBadger specifically relevant to this topic. "
            "Incorporate these EXACT endpoints, paths, and technical details when writing the blog to make it technically accurate and actionable.\n"
            "CRITICAL RULE FOR HYPERLINKS: Whenever you mention an API endpoint or a documentation page, you MUST use the real URLs provided in this documentation context to create markdown links (e.g., [Twitter Users API](https://docs.scrapebadger.com/twitter/users)). NEVER generate placeholder broken links like `[link]` or `href='#'`.\n\n"
            + docs_context
            + "\n\n---\n\n"
        )

    seo_section = ""
    if seo_feedback:
        seo_section = (
            "IMPORTANT — This is a REWRITE. The previous version FAILED its SEO audit. "
            "Read the feedback below carefully and fix every issue mentioned before writing:\n\n"
            + seo_feedback
            + "\n\n---\n\n"
        )

    repair_section = ""
    if repair_feedback:
        repair_section = (
            "USER REPAIR REQUEST: The user has seen the previous output and requested following CHANGES. "
            "You MUST fulfill these requests while maintaining the ScrapeBadger voice:\n\n"
            "FEEDBACK: " + repair_feedback
            + "\n\n---\n\n"
        )

    anti_patterns_section = ""
    if anti_patterns:
        anti_patterns_section = (
            "IMPORTANT — ANTI-PATTERNS: The user explicitly HATED the following phrases and sentence structures from your previous outputs. "
            "Do NOT use these phrases, and actively avoid writing sentences that sound remotely like them (e.g. fluffy transitions, generic marketing speak):\n\n"
            + anti_patterns
            + "\n\n---\n\n"
        )

    internal_links = discover_internal_links()
    internal_linking_section = ""
    if internal_links:
        internal_linking_section = (
            "### INTERNAL BLOG POSTS (FOR LINKING)\n"
            "Include exactly 1-2 links to relevant previous blog posts from this list. Use natural anchor text:\n\n"
            + internal_links
            + "\n\n---\n\n"
        )

    return (
        f"{few_shot}"
        f"{research_section}"
        f"{docs_section}"
        f"{seo_section}"
        f"{repair_section}"
        f"{anti_patterns_section}"
        f"{internal_linking_section}"
        f"Now write a new blog post using the style guide above.\n\n"
        f"CRITICAL STRUCTURAL RULES:\n"
        f"- START WITH A # H1 Main Title.\n"
        f"- USE Markdown tables for all comparisons. Tables MUST contain ONLY plain text (no colors).\n"
        f"- INCLUDE a ## FAQ section with at least 5 questions and answers.\n"
        f"- USE colored <span> blocks for status/tiers markers as defined in the style guide.\n\n"
        f"Topic: {TOPIC}\n"
        f"Primary Keyword: {PRIMARY_KEYWORD}\n"
        f"Secondary Keywords: {SECONDARY_KEYWORDS}\n"
        f"Target Word Count: Around {WORD_COUNT} words (RECOMMENDATION, not a hard limit). The text can be longer or shorter depending on the topic. Never cut content short to hit a number — cover the topic fully and completely.\n\n"
        f"Output only the blog post text. No meta-commentary. Use rich Markdown formatting (e.g. ## for headers, ** for bold) and triple backticks (```) for Inline Code Examples."
    )


def generate_blog(api_key: str, model_name: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = load_style_guide()
    user_message  = build_user_message()

    print(f"Calling {model_name}...")
    message = client.messages.create(
        model=model_name,
        max_tokens=16384,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def save_to_file(content: str):
    path = get_output_path()
    with open(path, "w") as f:
        f.write(content)
    print(f"Saved to {path}")


def write_to_sheet(content: str, topic: str, row_idx: int = None):
    if row_idx is None:
        row_idx = ROW_IDX
        
    creds  = Credentials.from_service_account_file(CREDENTIALS, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open_by_key(SHEET_ID).sheet1

    # Write generated blog to column F (the output column) and mark status in E
    sheet.update_acell(f"E{row_idx}", "done")
    sheet.update_acell(f"F{row_idx}", content)
    print(f"Written to Google Sheets (F{row_idx}).")


def load_keys() -> dict:
    """Read KEY=VALUE pairs from anthropic_key.txt."""
    keys = {}
    key_file = os.path.join(BASE_DIR, "anthropic_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys


def main():
    # ── Load inputs from Google Sheet FIRST ─────────────────────────────────
    load_blog_inputs_from_sheet()

    keys = load_keys()
    api_key = keys.get("ANTHROPIC_API_KEY", "").strip()
    model_name = keys.get("CLAUDE_MODEL", MODEL_FALLBACK).strip()

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in anthropic_key.txt")

    blog_content = generate_blog(api_key, model_name)
    save_to_file(blog_content)
    print("\nDone! Blog post generated successfully.")


if __name__ == "__main__":
    main()
