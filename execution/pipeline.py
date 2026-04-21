"""
pipeline.py

Master orchestrator for the full ScrapeBadger blog pipeline.
Runs all 8 agents in sequence (strict linear flow).

Flow:
  1. Deep Research Agent  → gathers info from Tavily, Perplexity, Exa, Firecrawl
  2. Docs Agent           → gathers API context from ScrapeBadger docs
  3. Blog Writer Agent    → generates plain text/markdown blog with Claude Sonnet
  4. SEO Checker Agent    → runs structural and semantic checks on the generated text
  5. HTML Designer Agent  → formats the text into raw, clean HTML
  6. Cover Image Agent    → generates a DALL-E 3 cover image based on ScrapeBadger style
  7. SEO Meta Agent       → generates title and description tags 
  8. Social Media Agent   → generates LinkedIn and Twitter promo texts
  9. Write to Sheet       → push final approved plain text blog to Google Sheets

Usage:
    python3 execution/pipeline.py

    # Skip research (use existing research file):
    python3 execution/pipeline.py --skip-research
    # Skip docs agent (use existing docs file):
    python3 execution/pipeline.py --skip-docs
"""

import os
import sys
import subprocess
import importlib.util

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_agent(filename: str):
    """Dynamically import an agent module from execution/."""
    path = os.path.join(BASE_DIR, "execution", filename)
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def print_header(step: str, total: int, current: int):
    bar = "█" * current + "░" * (total - current)
    print(f"\n{'='*60}")
    print(f"  [{bar}] Step {current}/{total}: {step}")
    print(f"{'='*60}\n")


def main():
    args           = sys.argv[1:]
    is_repair      = "--repair" in args
    skip_research  = "--skip-research" in args or is_repair
    skip_docs      = "--skip-docs" in args or is_repair
    no_telegram    = "--no-telegram" in args
    
    repair_file = os.path.join(BASE_DIR, ".tmp", "repair_feedback.txt")

    if is_repair:
        print(f"\n🚀 ScrapeBadger Content Pipeline: REPAIR MODE\n")
        if not os.path.exists(repair_file):
            print("⚠️ No repair feedback found in .tmp/repair_feedback.txt. Running standard generation.")
    else:
        # Standard run: Clear any old feedback to prevent pollution
        files_to_clear = [
            repair_file,
            os.path.join(BASE_DIR, ".tmp", "seo_feedback.txt"),
            os.path.join(BASE_DIR, ".tmp", "docs_context.txt"),
            os.path.join(BASE_DIR, ".tmp", "seo_report_*.txt") # Note: glob handled below if needed
        ]
        import glob
        for f_pattern in files_to_clear:
            for f_path in glob.glob(f_pattern):
                if os.path.exists(f_path):
                    os.remove(f_path)
        print("🧹 Cleared old feedback/context files.")
        print(f"\n🚀 ScrapeBadger 8-Agent Content Pipeline Starting\n")

    # ── STEP 1: Deep Research ──────────────────────────────────────────────────
    if not skip_research:
        print_header("Deep Research Agent", 8, 1)
        research = load_agent("deep_research_agent.py")
        research.main()
    else:
        print("⏭️  Skipping research (using existing research file)")

    # ── STEP 2: Docs Agent ──────────────────────────────────────────────────
    if not skip_docs:
        print_header("API Docs Agent", 8, 2)
        docs_agent = load_agent("docs_agent.py")
        docs_agent.main()
    else:
        print("⏭️  Skipping docs (using existing docs file)")

    # ── STEP 3: Blog Writer ───────────────────────────────────────────────────
    print_header("Blog Writer Agent", 8, 3)
    writer = load_agent("generate_blog_claude.py")
    writer.main()
    topic = writer.TOPIC
    md_file_path = writer.get_output_path()

    # ── STEP 4: SEO Checker Agent ───────────────────────────────────────────
    print_header("SEO Checker Agent", 8, 4)
    checker = load_agent("seo_checker_agent.py")
    # Get primary keyword from the writer's inputs
    primary_kw = writer.PRIMARY_KEYWORD
    checker.main(blog_file=md_file_path, keyword=primary_kw)

    # ── STEP 5: HTML Designer Agent ───────────────────────────────────────────
    print_header("HTML Designer Agent", 8, 5)
    designer = load_agent("html_designer_agent.py")
    designer.main(blog_file=md_file_path)

    # ── STEP 6: Blog Cover Generator (Google Imagen 4.0) ──────────────────────
    print_header("Cover Image Generator", 11, 6)
    try:
        print("Attempting to generate cover with Google Imagen 4.0...")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "generate_blog_images_google.py"), topic], check=True)
    except subprocess.CalledProcessError:
        print("⚠️ Google Imagen failed (e.g. quota limit). Falling back to OpenAI DALL-E 3...")
        try:
            subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "generate_blog_cover.py"), topic], check=True)
        except subprocess.CalledProcessError:
            print("⚠️ DALL-E 3 also failed. Falling back to Nano Banana...")
            try:
                subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "generate_blog_images_nano.py"), topic], check=True)
            except subprocess.CalledProcessError:
                print("❌ ALL Image generators failed. Continuing pipeline without a new cover image.")

    # ── STEP 7: SEO Meta Data Generator ─────────────────────────────────────────
    print_header("SEO Meta Generator", 8, 7)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "generate_seo_meta.py"), md_file_path, primary_kw], check=True)

    # ── STEP 8: Social Media Posts Generator ──────────────────────────────────
    print_header("Social Media Agent", 11, 8)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "generate_social_posts.py"), md_file_path], check=True)

    # ── STEP 9: Consolidate Everything ────────────────────────────────────────
    print_header("Consolidate Agent", 11, 9)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "consolidate_blog.py"), md_file_path], check=True)

    # ── STEP 10: HTML Export ──────────────────────────────────────────────────
    print_header("HTML Export Agent", 11, 10)
    consolidated_md = f"{os.path.splitext(md_file_path)[0]}_CONSOLIDATED.md"
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "export_to_html.py"), consolidated_md], check=True)

    # ── TELEGRAM NOTIFICATION ───────────────────────────────────────────────
    if not no_telegram:
        print_header("Telegram Notification", 11, 11)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "execution", "send_to_telegram.py"), topic, consolidated_md], check=False)
    else:
        print("\n⏭️ Skipping Telegram Notification (Batch Mode active).")

    print("\n" + "=" * 60)
    print("  🎉 Pipeline complete! Results saved locally.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
