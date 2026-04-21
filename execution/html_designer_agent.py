"""
html_designer_agent.py

HTML Designer Agent — the third step in the ScrapeBadger blog pipeline.

Reads the generated blog post (Markdown/Text) and uses Claude to format it
into a clean, beautifully structured HTML document based on strict rules.

Usage:
    python3 execution/html_designer_agent.py
"""

import os
import anthropic

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_FILE   = os.path.join(BASE_DIR, "anthropic_key.txt")
MODEL_FALLBACK = "claude-sonnet-4-6"

# ── HTML Design Prompt ─────────────────────────────────────────────────────────
DESIGNER_SYSTEM_PROMPT = """You are a professional blog designer. Transform plain text blog posts into 
clean, beautifully structured HTML documents.

Rules:
1. Title → <h1> at the top
2. Sections → <h2> or <h3> as appropriate
3. Key terms or important phrases → <strong>
4. Lists → <ul>/<ol> with proper nesting
5. Code → <pre><code> blocks
6. Long quotes or callouts → <blockquote>
7. Do not add intros, disclaimers, or commentary — output HTML only
8. Preserve the original tone and wording exactly
9. Visual style: clean, minimal, generous whitespace — no decorative elements
10. List alignment: ul and ol elements must have padding-left: 1.2em and margin-left: 0 so bullet points align flush with the body text column, not indented further right. Always include this CSS in the <style> block:
    ul, ol { padding-left: 1.2em; margin-left: 0; }
    li { margin-bottom: 0.3em; }"""


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
def load_blog(blog_file: str) -> str:
    with open(blog_file, "r") as f:
        return f.read()


# ── Main Generator ────────────────────────────────────────────────────────────
def generate_html(api_key: str, blog_text: str, model_name: str) -> str:
    print(f"  Calling Claude ({model_name}) to format HTML...")
    client = anthropic.Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model=model_name,
        max_tokens=8192,
        system=DESIGNER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Convert the following text into structured HTML per your instructions:\n\n{blog_text}"
        }],
    )
    
    html_output = message.content[0].text.strip()
    
    # Clean up standard markdown code block formatting if Claude accidentally added it
    if html_output.startswith("```html"):
        html_output = html_output[7:]
    elif html_output.startswith("```"):
        html_output = html_output[3:]
    if html_output.endswith("```"):
        html_output = html_output[:-3]
        
    return html_output.strip()


def main(blog_file: str = None):
    print("🎨 HTML Designer Agent\n")
    keys = load_keys()
    api_key = keys.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in anthropic_key.txt")

    if not blog_file:
        raise ValueError("blog_file argument is required")

    blog_text = load_blog(blog_file)
    print(f"  Loaded raw blog text: {len(blog_text):,} chars")
    
    model_name = keys.get("CLAUDE_MODEL", MODEL_FALLBACK).strip()
    html_content = generate_html(api_key, blog_text, model_name)
    
    output_file = os.path.splitext(blog_file)[0] + ".html"
    
    with open(output_file, "w") as f:
        f.write(html_content)
        
    print(f"  ✅ HTML formatted and saved to: {output_file}")

if __name__ == "__main__":
    main()
