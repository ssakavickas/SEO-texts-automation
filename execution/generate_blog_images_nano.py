import os
import sys
import re
import base64
from google import genai
from google.genai import types


def get_slug(text: str):
    """Generate a clean slug from text - EXACT MATCH to generate_blog_claude.py"""
    slug = text.lower().strip()
    slug = slug.replace(" ", "_").replace(":", "").replace("?", "").replace("'", "").replace("(","").replace(")","").replace("\u201c","").replace("\u201d","").replace("\u2019","").replace("/","_")
    slug = re.sub(r'_+', '_', slug)
    if len(slug) > 50: slug = slug[:50]
    if slug.endswith("_"): slug = slug[:-1]
    return slug

def load_keys():
    """Read GOOGLE_API_KEY from anthropic_key.txt."""
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

def generate_nano_image(api_key, topic):
    print(f"🎨 Generating image with Nano Banana model for: '{topic}'...")
    client = genai.Client(api_key=api_key)
    prompt = (
        f"A professional, high-quality modern blog post cover image about: '{topic}'. "
        "Style: Clean vector art, cybersecurity and data monitoring aesthetic. "
        "Visual elements: An anthropomorphic badger wearing thick-rimmed black glasses and a dark hoodie as the primary character. "
        "Abstract data streams, bird-like silhouettes (hinting at Twitter/X), "
        "magnifying glass scanning digital social media profiles, blue and dark tech color palette. "
        "No robots or humans allowed. ABSOLUTELY NO SCREENS, NO MONITORS, NO DASHBOARDS. ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO LABELS, NO WATERMARKS. Premium, sharp, futuristic design."
    )
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"  [Attempt {attempt+1}/{max_retries}] Generating Nano image...")
            result = client.models.generate_images(
                model='imagen-3.0-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9"
                )
            )
            
            if result.generated_images:
                image = result.generated_images[0]
                
                # --- Vision Validation ---
                print("  👁️ Verifying image with Gemini Vision to ensure NO TEXT is present...")
                vision_prompt = "Does this image contain any visible text, words, letters, typography, watermarks, or numbers? Respond with exactly one word: either YES or NO."
                vision_result = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=image.image_bytes, mime_type='image/png'),
                        vision_prompt
                    ]
                )
                
                has_text = "YES" in vision_result.text.strip().upper()
                if has_text:
                    print("  ❌ Text detected by Vision model! Discarding and retrying...")
                    continue

                # --- Content Validation (badger, no humans, no robots) ---
                print("  👁️ Verifying image content (badger present, no humans/robots)...")
                content_prompt = (
                    "Analyze this image. Answer these 3 questions with YES or NO:\n"
                    "1. Is there an anthropomorphic badger (animal with glasses/hoodie) as the main central character?\n"
                    "2. Are there any humans, people, or human silhouettes in this image?\n"
                    "3. Are there any robots or drones in this image?\n"
                    "Reply EXACTLY in this format:\nBADGER:YES or NO\nHUMANS:YES or NO\nROBOTS:YES or NO"
                )
                content_result = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=image.image_bytes, mime_type='image/png'),
                        content_prompt
                    ]
                )
                content_text = content_result.text.strip().upper()
                print(f"  🤖 Content check: {content_result.text.strip()}")

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

                # Save the image with dynamic slug-based filename
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                slug = get_slug(topic)
                output_path = os.path.join(base_dir, f"{slug}_blog_cover.png")
                
                with open(output_path, "wb") as f:
                    f.write(image.image_bytes)
                
                print(f"✅ Success! Image saved: {output_path}")
                return output_path
            else:
                print("⚠️ Error: Model generated no images.")
                
        except Exception as e:
            print(f"❌ ERROR generating image attempt {attempt+1}: {e}")
            
    print("❌ Failed to generate a clean Nano image without text after max retries.")
    return None

def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "Twitter Competitor Tracking Without Official API"
    keys = load_keys()
    api_key = keys.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY not found in anthropic_key.txt")
        sys.exit(1)
        
    generate_nano_image(api_key, topic)

if __name__ == "__main__":
    main()
