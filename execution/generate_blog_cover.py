"""
execution/generate_blog_cover.py

This script automates the image creation process:
1. Reads the ScrapeBadger sitemap and extracts cover URLs from existing articles.
2. Uses GPT-4o Vision to analyze the art style and colors of those images.
3. Uses DALL-E 3 to generate a new image for the desired topic, matching the style.
4. Saves the result as a .png file.

Usage:
python3 execution/generate_blog_cover.py "Your New Article Topic"
"""

import os
import sys
import requests
import re
from bs4 import BeautifulSoup
from openai import OpenAI


def get_slug(text: str):
    """Generate a clean slug from text - EXACT MATCH to generate_blog_claude.py"""
    slug = text.lower().strip()
    slug = slug.replace(" ", "_").replace(":", "").replace("?", "").replace("'", "").replace("(","").replace(")","").replace("\u201c","").replace("\u201d","").replace("\u2019","").replace("/","_")
    slug = re.sub(r'_+', '_', slug)
    if len(slug) > 50: slug = slug[:50]
    if slug.endswith("_"): slug = slug[:-1]
    return slug

def load_keys():
    keys = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_file = os.path.join(base_dir, "anthropic_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys

keys = load_keys()
OPENAI_API_KEY = keys.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    # Fallback to .env just in case
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
    print("❌ ERROR: OPENAI_API_KEY not found in anthropic_key.txt or .env file.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_reference_image_urls(limit=3) -> list[str]:
    print(f"🔍 Searching for {limit} latest ScrapeBadger image examples...")
    sitemap_url = "https://scrapebadger.com/sitemap.xml"
    response = requests.get(sitemap_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(response.text, "xml")
    
    # Find all pages with dates
    urls_with_dates = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        lastmod = url_node.find("lastmod")
        if loc and re.match(r"https://scrapebadger\.com/blog/.+", loc.text.strip()):
            date_str = lastmod.text.strip() if lastmod else "2000-01-01"
            urls_with_dates.append((loc.text.strip(), date_str))
            
    # Sort from newest to oldest
    urls_with_dates.sort(key=lambda x: x[1], reverse=True)
    
    image_urls = []
    for url, date_str in urls_with_dates:
        try:
            post_soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=10).text, "html.parser")
            og_image = post_soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                img_url = og_image["content"]
                if img_url not in image_urls:  # Avoid duplicates
                    image_urls.append(img_url)
                    print(f"   📸 Found image from: {url}")
                if len(image_urls) >= limit: 
                    break
        except Exception as e:
            pass
            
    print(f"✅ Found image examples: {len(image_urls)}")
    return image_urls

def extract_style_prompt(image_urls: list[str]) -> str:
    print(f"🧠 Analyzing unified style from {len(image_urls)} images (GPT-4o Vision)...")
    
    content_list = [{"type": "text", "text": "Extract a highly detailed style prompt based on these reference images. Do not describe specific subjects, ONLY the unified art style, color palette, geometric shapes, and atmosphere."}]
    
    for url in image_urls:
        content_list.append({"type": "image_url", "image_url": {"url": url}})
        
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert art director. Describe the exact visual style, color palette, geometric shapes, and atmosphere based on the provided reference images."},
            {"role": "user", "content": content_list}
        ],
        max_tokens=300
    )
    return response.choices[0].message.content

def generate_new_cover(topic: str, style_parameters: str) -> str:
    print(f"🎨 Generating image for topic: '{topic}' (DALL-E 3)...")
    full_prompt = f"Create a professional modern blog post cover image about the topic: \"{topic}\". CRITICAL STYLE REQUIREMENTS: {style_parameters}. RULES: 1. MUST feature an anthropomorphic badger in thick-rimmed glasses and a dark hoodie. 2. NO robots, drones, or humans. 3. ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO LABELS, NO WATERMARKS. 4. Maintain the exact modern vector art style. 5. Include subtle abstract tech representations."
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  [Attempt {attempt+1}/{max_retries}] Generating DALL-E image...")
            response = client.images.generate(model="dall-e-3", prompt=full_prompt, size="1024x1024", quality="standard", n=1)
            image_url = response.data[0].url
            
            # --- Vision Validation ---
            print("  👁️ Verifying image with GPT-4o Vision to ensure NO TEXT is present...")
            vision_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Does this image contain any visible text, words, letters, typography, watermarks, or numbers? Respond with exactly one word: either YES or NO."},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=10
            )
            has_text = "YES" in vision_response.choices[0].message.content.strip().upper()
            if has_text:
                print("  ❌ Text detected by Vision model! Discarding and retrying...")
                continue

            # --- Content Validation (badger, no humans, no robots) ---
            print("  👁️ Verifying image content (badger present, no humans/robots)...")
            content_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": (
                                "Analyze this image. Answer these 3 questions with YES or NO:\n"
                                "1. Is there an anthropomorphic badger (animal with glasses/hoodie) as the main central character?\n"
                                "2. Are there any humans, people, or human silhouettes?\n"
                                "3. Are there any robots or drones?\n"
                                "Reply EXACTLY in format:\nBADGER:YES or NO\nHUMANS:YES or NO\nROBOTS:YES or NO"
                            )},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=50
            )
            content_text = content_response.choices[0].message.content.strip().upper()
            print(f"  🤖 Content check: {content_response.choices[0].message.content.strip()}")

            has_badger = "BADGER:YES" in content_text or "BADGER: YES" in content_text
            has_humans = "HUMANS:YES" in content_text or "HUMANS: YES" in content_text
            has_robots = "ROBOTS:YES" in content_text or "ROBOTS: YES" in content_text

            if not has_badger:
                print("  ❌ No badger detected! Discarding and retrying...")
                continue
            if has_humans:
                print("  ❌ Humans detected! Discarding and retrying...")
                continue
            if has_robots:
                print("  ❌ Robots detected! Discarding and retrying...")
                continue
            # -------------------------

            print("  ✅ Image is clean (no text, badger present, no humans/robots).")
            return image_url
            
        except Exception as e:
            print(f"❌ ERROR generating image attempt {attempt+1}: {e}")
            
    print("❌ Failed to generate a clean DALL-E image without text after max retries.")
    return None

def download_image(url: str, filepath: str):
    response = requests.get(url, stream=True)
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(8192): f.write(chunk)
    print(f"💾 Image saved: {filepath}")

def main():
    if len(sys.argv) < 2: sys.exit(1)
    topic = sys.argv[1]
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    ref_urls = get_reference_image_urls(limit=1)
    if not ref_urls: sys.exit(1)
    style_prompt = extract_style_prompt(ref_urls)
    dalle_url = generate_new_cover(topic, style_prompt)

    if not dalle_url:
        print("❌ Failed to generate a valid cover image.")
        sys.exit(1)

    # Save the image with dynamic slug-based filename
    slug = get_slug(topic)
    filepath = os.path.join(BASE_DIR, f"{slug}_blog_cover.png")
    download_image(dalle_url, filepath)

    print(f"\n🎉 ALL DONE! New image generated and saved to: {filepath}")

if __name__ == "__main__":
    main()
