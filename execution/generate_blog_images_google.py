import os
import sys
import re
from google import genai
from google.genai import types

def get_slug(text: str):
    """Generate a clean slug from text - EXACT MATCH to generate_blog_claude.py"""
    slug = text.lower().strip()
    slug = slug.replace(" ", "_").replace(":", "").replace("?", "").replace("'", "").replace("(","").replace(")","").replace("“","").replace("”","").replace("’","").replace("/","_")
    slug = re.sub(r'_+', '_', slug)
    if len(slug) > 50: slug = slug[:50]
    if slug.endswith("_"): slug = slug[:-1]
    return slug

def load_keys():
# ... (rest of load_keys)
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

def generate_google_image(api_key, topic):
    print(f"🎨 Generating unique image for theme: '{topic}'...")
    client = genai.Client(api_key=api_key)
    
    # 1. Provide only text instructions (Reference images have been removed to prevent hallucinations like 'carbonara')
    ref_images = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 2. Stage 1: Ask Gemini to describe the scene
    prompt_generator_instruction = (
        f"Create a descriptive visual prompt for a 2D flat vector illustration about the topic: '{topic}'.\n\n"
        "Rules for the scene:\n"
        "- The style must be clean 2D flat vector art (minimalist, sharp outlines, no 3D, no gradients).\n"
        "- The PRIMARY and CENTRAL character is an anthropomorphic badger wearing thick-rimmed black glasses and a dark hoodie. He is the ONLY character allowed.\n"
        "- The scene must NOT contain any humans, people, or silhouettes. The world is populated ONLY by the badger and topic-related abstract elements or icons.\n"
        "- CRITICAL: The image must NOT contain any text, words, letters, numbers, or typography.\n"
        "- You MUST include relevant visual elements that fit the specific topic (e.g. abstract data nodes, servers, gears, cables, clouds), BUT ABSOLUTELY NO SCREENS, NO MONITORS, NO DASHBOARDS to prevent any fake text generation.\n"
        "- Do NOT use any other human-like characters or animals. The badger is the one doing the work.\n"
        "- Use colors and objects that logically match the theme of the topic.\n"
        "- Style: 100% clean 2D flat vector art, minimalist, sharp outlines, NO 3D, NO shadows, NO gradients."
    )
    
    scene_description = f"A professional 2D flat vector illustration showing {topic} with thematic elements matching the topic and an anthropomorphic badger character."
    try:
        contents = [prompt_generator_instruction] + ref_images if ref_images else [prompt_generator_instruction]
        
        prompt_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents
        )
        scene_description = prompt_response.text.strip()
        # Post-process to remove any mention of text/labels from the AI-generated description
        text_forbidden_words = [
            "text", "label", "word", "letter", "font", "character", "alphabet",
            "writing", "script", "scrapebadger", "sign", "banner", "screen",
            "person", "people", "human", "man", "woman", "boy", "girl",
            "robot", "machine", "drone", "silhouette", "monitor", "dashboard"
        ]
        for forbidden in text_forbidden_words:
            scene_description = re.sub(rf"\b{forbidden}\b", "", scene_description, flags=re.IGNORECASE)
        
        print(f"  📝 Generated scene description: {scene_description[:100]}...")
    except Exception as e:
        print(f"  ⚠️ Error generating description: {e}. Using fallback.")

    # 3. Combine with technical constraints for Imagen
    final_prompt = (
        f"{scene_description} "
        "STYLE: CLEAN 2D FLAT VECTOR ART. MINIMALIST. "
        "CHARACTER: AN ANTHROPOMORPHIC BADGER WITH THICK-RIMMED GLASSES AND A HOODIE. "
        "CRITICAL FORBIDDEN: ABSOLUTELY NO HUMANS. NO PEOPLE. NO SILHOUETTES. NO OTHER ANIMALS. "
        "ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO FONTS, NO LABELS, NO WATERMARKS, NO SIGNATURES. "
    )

    
    # Add repair feedback if available
    repair_file = os.path.join(base_dir, ".tmp", "repair_feedback.txt")
    if os.path.exists(repair_file):
        try:
            with open(repair_file, "r") as f:
                repair_feedback = f.read().strip()
                if repair_feedback:
                    final_prompt += f" REFINEMENT: {repair_feedback}"
                    print(f"  🎨 Applied repair feedback: {repair_feedback}")
        except:
            pass
    
    # 4. Generate image with Imagen and Validate with Vision
    max_retries = 15
    for attempt in range(max_retries):
        try:
            print(f"  [Attempt {attempt+1}/{max_retries}] Generating image...")
            result = client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=final_prompt + " STRICTLY FORBIDDEN: text, words, letters, typography, watermark, signature, font, writing, alphabet, signs, banners, numbers.",
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9"
                )
            )
            
            if result.generated_images:
                image_obj = result.generated_images[0].image
                
                # --- Vision Validation ---
                print("  👁️ Verifying image with Gemini Vision to ensure NO TEXT is present...")
                vision_prompt = (
                    "Analyze this image carefully. "
                    "Does this image contain any legible human language, written words, alphabet letters, typography, "
                    "watermarks, signatures, or numbers? "
                    "IMPORTANT: The blue bird icon (Twitter logo) is NOT a letter. "
                    "Abstract shapes, geometric nodes, and unlabeled data flows are NOT text. "
                    "If you see EVEN A SINGLE letter or number anywhere, reply with ONLY the word: YES. "
                    "If the image contains NO text whatsoever and is purely pictorial/abstract, reply with ONLY the word: NO."
                )
                vision_result = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=image_obj.image_bytes, mime_type='image/png'),
                        vision_prompt
                    ]
                )
                
                vision_text = vision_result.text.strip().upper()
                print(f"  🤖 Vision model answered: '{vision_result.text.strip()}'")
                
                has_text = "YES" in vision_text
                if has_text:
                    print("  ❌ Text detected by Vision model! Discarding and retrying...")
                    continue

                # --- Content Validation (badger, no humans, no robots) ---
                print("  👁️ Verifying image content (badger present, no humans/robots)...")
                content_prompt = (
                    "Analyze this image. Answer these 2 questions with YES or NO:\n"
                    "1. Is there an anthropomorphic badger (animal with glasses/hoodie) as the main central character?\n"
                    "2. Are there any humans, people, or human silhouettes in this image?\n"
                    "Reply EXACTLY in this format:\nBADGER:YES or NO\nHUMANS:YES or NO"
                )
                content_result = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=image_obj.image_bytes, mime_type='image/png'),
                        content_prompt
                    ]
                )
                content_text = content_result.text.strip().upper()
                print(f"  🤖 Content check: {content_result.text.strip()}")

                has_badger = "BADGER:YES" in content_text or "BADGER: YES" in content_text
                has_humans = "HUMANS:YES" in content_text or "HUMANS: YES" in content_text

                if not has_badger:
                    print("  ❌ No badger detected! Discarding and retrying...")
                    continue
                if has_humans:
                    print("  ❌ Humans detected! Discarding and retrying...")
                    continue
                # -------------------------

                print("  ✅ Image is clean (no text, badger present, no humans).")
                slug = get_slug(topic)
                output_path = f"{slug}_blog_cover.png"
                output_abs_path = os.path.join(base_dir, output_path)
                
                with open(output_abs_path, "wb") as f:
                    f.write(image_obj.image_bytes)
                
                print(f"✅ Success! Image saved: {output_abs_path}")
                return output_abs_path
            else:
                print("⚠️ Error: Model generated no images.")
        except Exception as e:
            print(f"❌ Error during image generation/validation attempt {attempt+1}: {e}")
            import time
            time.sleep(5)  # Prevent spamming API on repeated errors
            
    print("❌ Failed to generate a clean image without text after max retries.")
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 execution/generate_blog_images_google.py \"Topic Name\"")
        sys.exit(1)
        
    topic = sys.argv[1]
    keys = load_keys()
    api_key = keys.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY not found in anthropic_key.txt")
        sys.exit(1)
        
    success = generate_google_image(api_key, topic)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
