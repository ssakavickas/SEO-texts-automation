"""
seo_checker_agent.py

SEO Checker Agent — the third step in the ScrapeBadger blog pipeline.

Reads the generated blog post and runs a two-layer SEO audit:
  1. Structural checks (fast, no API needed):
     - Word count
     - Primary keyword presence & density
     - Title / H1 detection
     - Meta description presence & length
     - URL slug presence
     - Section count

  2. Claude-powered semantic audit:
     - Readability & flow
     - Keyword naturalness
     - Missing SEO opportunities
     - Specific rewrite suggestions

Outputs a scored report to .tmp/seo_report_[timestamp].txt
Optionally prints a pass/fail summary to terminal.

Usage:
    python3 execution/seo_checker_agent.py
"""

import os
import re
import anthropic
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_FILE   = os.path.join(BASE_DIR, "anthropic_key.txt")
BLOG_FILE   = os.path.join(BASE_DIR, "twitter_competitor_tracking_blog.md")
OUTPUT_DIR  = os.path.join(BASE_DIR, ".tmp")
MODEL       = "claude-sonnet-4-5"
SEO_PASS_THRESHOLD = 65   # minimum structural score % to pass without rewrite

# Defaults (can be overridden by main parameters)
PRIMARY_KEYWORD_DEFAULT  = "tracking competitors twitter"
TARGET_WORD_COUNT_MIN = 800   # minimum only — no max limit, word count is a recommendation
META_DESC_LENGTH  = (120, 160)     # characters
KEYWORD_DENSITY   = (0.5, 2.5)     # percent


# ── Key Loader ────────────────────────────────────────────────────────────────
def load_keys() -> dict:
    keys = {}
    with open(KEYS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys


# ── Blog Reader ───────────────────────────────────────────────────────────────
def load_blog(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Blog file not found: {file_path}")
    with open(file_path, "r") as f:
        return f.read()


# ════════════════════════════════════════════════════════════════════════
# LAYER 1: Structural Checks
# ════════════════════════════════════════════════════════════════════════

def check_word_count(text: str) -> tuple[int, str, bool]:
    count = len(text.split())
    ok = count >= TARGET_WORD_COUNT_MIN
    status = "✅" if ok else f"⚠️  Too short (minimum {TARGET_WORD_COUNT_MIN})"
    return count, status, ok


def check_keyword_density(text: str, keyword: str) -> tuple[float, str, bool]:
    words = text.lower().split()
    kw_words = keyword.lower().split()
    matches = sum(
        1 for i in range(len(words) - len(kw_words) + 1)
        if words[i:i+len(kw_words)] == kw_words
    )
    total_words = len(words)
    density = (matches / total_words * 100) if total_words else 0
    ok = KEYWORD_DENSITY[0] <= density <= KEYWORD_DENSITY[1]
    status = "✅" if ok else ("⚠️  Too low" if density < KEYWORD_DENSITY[0] else "⚠️  Too high (keyword stuffing)")
    return round(density, 2), status, ok


def check_keyword_in_title(text: str, keyword: str) -> tuple[bool, str]:
    first_line = text.strip().split("\n")[0].lower()
    found = keyword.lower() in first_line
    return found, "✅" if found else "❌ Primary keyword missing from title"


def check_meta_description(text: str) -> tuple[str, str, bool]:
    match = re.search(r"Meta Description[:\s]+(.+)", text, re.IGNORECASE)
    if not match:
        return "", "❌ Meta description not found", False
    desc = match.group(1).strip()
    length = len(desc)
    ok = META_DESC_LENGTH[0] <= length <= META_DESC_LENGTH[1]
    status = "✅" if ok else f"⚠️  Length {length} chars (target: {META_DESC_LENGTH[0]}–{META_DESC_LENGTH[1]})"
    return desc, status, ok


def check_url_slug(text: str) -> tuple[str, str, bool]:
    match = re.search(r"URL Slug[:\s]+(.+)", text, re.IGNORECASE)
    if not match:
        return "", "❌ URL slug not found", False
    slug = match.group(1).strip()
    ok = bool(slug) and " " not in slug
    status = "✅" if ok else "⚠️  Slug contains spaces or is invalid"
    return slug, status, ok


def check_section_count(text: str) -> tuple[int, str, bool]:
    # Count ALL-CAPS section headers (our plain text format)
    sections = re.findall(r"^[A-Z][A-Z\s\(\)/&]{3,}$", text, re.MULTILINE)
    count = len(sections)
    ok = count >= 4
    status = "✅" if ok else f"⚠️  Only {count} sections detected (aim for 5+)"
    return count, status, ok


def run_structural_checks(text: str, keyword: str) -> dict:
    print("\n── Layer 1: Structural Checks ──────────────────────────")
    results = {}

    word_count, wc_status, wc_ok = check_word_count(text)
    print(f"  Word Count:        {word_count} words  {wc_status}")
    results["word_count"] = {"value": word_count, "ok": wc_ok, "status": wc_status}

    density, dens_status, dens_ok = check_keyword_density(text, keyword)
    print(f"  Keyword Density:   {density}%  {dens_status}")
    results["keyword_density"] = {"value": density, "ok": dens_ok, "status": dens_status}

    kw_title, kw_title_status = check_keyword_in_title(text, keyword)
    print(f"  Keyword in Title:  {kw_title_status}")
    results["keyword_in_title"] = {"value": kw_title, "ok": kw_title, "status": kw_title_status}

    meta_desc, meta_status, meta_ok = check_meta_description(text)
    print(f"  Meta Description:  {meta_status}")
    results["meta_description"] = {"value": meta_desc, "ok": meta_ok, "status": meta_status}

    slug, slug_status, slug_ok = check_url_slug(text)
    print(f"  URL Slug:          {slug_status}")
    results["url_slug"] = {"value": slug, "ok": slug_ok, "status": slug_status}

    sections, sec_status, sec_ok = check_section_count(text)
    print(f"  Section Count:     {sections} sections  {sec_status}")
    results["sections"] = {"value": sections, "ok": sec_ok, "status": sec_status}

    passed = sum(1 for r in results.values() if r["ok"])
    total  = len(results)
    score  = round(passed / total * 100)
    print(f"\n  Structural Score:  {passed}/{total} ({score}%)")
    results["structural_score"] = score

    return results


# ════════════════════════════════════════════════════════════════════════
# LAYER 2: Claude-Powered Semantic SEO Audit
# ════════════════════════════════════════════════════════════════════════

SEO_SYSTEM_PROMPT = """You are a senior SEO specialist with deep expertise in technical content marketing.
Your job is to audit a blog post and provide specific, actionable SEO feedback.

Focus on:
1. Keyword usage — is the primary keyword used naturally throughout? In key positions?
2. Content depth — does it cover the topic comprehensively enough to rank?
3. Search intent match — does it answer what someone searching this keyword actually wants?
4. Internal linking opportunities — what related topics could be linked?
5. Content gaps — what important subtopics are missing that competitors likely cover?
6. Title & heading optimization — are they compelling and keyword-rich?
7. Readability — short paragraphs, clear structure, scannable?

Output your audit as:
SEO SCORE: [0-100]

STRENGTHS:
- [list 3-5 things done well]

ISSUES:
- [list specific problems with line references if possible]

RECOMMENDATIONS:
- [list 5-10 specific, actionable improvements ranked by impact]

MISSING CONTENT:
- [list subtopics or sections the article should add to compete in search]"""


def run_semantic_audit(api_key: str, blog_text: str, keyword: str) -> str:
    print("\n── Layer 2: Claude Semantic SEO Audit ─────────────────")
    print(f"  Target Keyword: {keyword}")
    print("  Calling Claude Sonnet...")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SEO_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Primary keyword to optimize for: \"{keyword}\"\n\n"
                f"Here is the blog post to audit:\n\n{blog_text}"
            )
        }],
    )
    audit = message.content[0].text
    print("  ✅ Audit complete")
    return audit


# ── Save Report ───────────────────────────────────────────────────────────────
def save_report(structural: dict, semantic: str, file_path: str, keyword: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"seo_report_{timestamp}.txt")

    lines = [
        "SEO AUDIT REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Blog file: {file_path}",
        f"Primary Keyword: {keyword}",
        "",
        "=" * 60,
        "LAYER 1: STRUCTURAL CHECKS",
        "=" * 60,
    ]

    for key, val in structural.items():
        if key == "structural_score":
            continue
        lines.append(f"{key:20s}: {val['status']}")

    lines.append(f"\nStructural Score: {structural['structural_score']}%")
    lines.append("")
    lines.append("=" * 60)
    lines.append("LAYER 2: SEMANTIC SEO AUDIT (Claude)")
    lines.append("=" * 60)
    lines.append(semantic)

    with open(path, "w") as f:
        f.write("\n".join(lines))

    print(f"\n📄 SEO report saved: {path}")
    return path


# ── Main ──────────────────────────────────────────────────────────────────────
def save_feedback(semantic: str):
    """Save SEO feedback to .tmp/seo_feedback.txt for the blog writer to read."""
    path = os.path.join(OUTPUT_DIR, "seo_feedback.txt")
    with open(path, "w") as f:
        f.write("SEO FEEDBACK FOR REWRITE\n\n")
        f.write(semantic)
    print(f"  Feedback saved: {path}")
    return path


def main(blog_file: str = None, keyword: str = None) -> tuple[int, str]:
    """Returns (structural_score, semantic_audit) for use by pipeline.py."""
    import sys
    
    # Handle CLI arguments if called directly
    if blog_file is None:
        if len(sys.argv) > 1:
            blog_file = sys.argv[1]
        else:
            blog_file = BLOG_FILE # default from old constant if not specified

    if keyword is None:
        if len(sys.argv) > 2:
            keyword = sys.argv[2]
        else:
            keyword = PRIMARY_KEYWORD_DEFAULT

    print(f"🔍 SEO Checker Agent for: {keyword}\n")
    keys    = load_keys()
    api_key = keys.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in anthropic_key.txt")

    blog_text = load_blog(blog_file)
    print(f"Blog loaded: {len(blog_text):,} chars")

    # Layer 1 — fast structural checks
    structural = run_structural_checks(blog_text, keyword)
    score = structural["structural_score"]

    # Layer 2 — Claude semantic audit
    semantic = run_semantic_audit(api_key, blog_text, keyword)

    print("\n" + "=" * 50)
    print(semantic)

    # Save full report + feedback file
    save_report(structural, semantic, blog_file, keyword)
    save_feedback(semantic)

    passed = score >= SEO_PASS_THRESHOLD
    print(f"\n{'✅ SEO PASSED' if passed else '❌ SEO FAILED'} (score: {score}%, threshold: {SEO_PASS_THRESHOLD}%)")
    print("✅ SEO audit complete!")
    return score, semantic


if __name__ == "__main__":
    main()
