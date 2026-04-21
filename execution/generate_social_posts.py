"""
execution/generate_social_posts.py

Šis skriptas perskaito nurodytą blogo straipsnį ir, naudodamas Claude AI, 
sugeneruoja jam du reklaminius tekstus:
1. Skirtą LinkedIn (profesionalus, įtraukiantis, kviečiantis padiskutuoti).
2. Skirtą Twitter / X (trumpas, kabinantis, su hashtagais).

Kiekvienas tekstas išsaugomas į atskirą .txt failą.

Naudojimas:
python3 execution/generate_social_posts.py "kelias/iki/blogo_failo.md"
"""

import os
import sys
from anthropic import Anthropic

def get_config():
    """Ištraukia Anthropic raktą ir modelį iš anthropic_key.txt arba .env"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    
    if not api_key:
        try:
            with open("anthropic_key.txt", "r") as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                    elif line.startswith("CLAUDE_MODEL="):
                        model_val = line.split("=", 1)[1].strip()
                        model = model_val
        except FileNotFoundError:
            pass
            
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found. Please add it to anthropic_key.txt")
        sys.exit(1)
        
    return api_key, model

def generate_social_content(file_path: str, api_key: str, model: str):
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File '{file_path}' not found.")
        sys.exit(1)
        
    with open(file_path, "r", encoding="utf-8") as f:
        article_content = f.read()

    print(f"📄 Reading article for social media posts creation: {file_path}")
    print(f"🤖 Calling Claude ({model})...\n")

    client = Anthropic(api_key=api_key)

    system_prompt = """
    Your task is to act as an expert social media manager. 
    You will read a blog post and generate two distinct social media promotional posts.
    
    OUTPUT FORMAT:
    Do not use JSON. Output the posts exactly wrapped in these XML tags:
    <linkedin>
    [LinkedIn Post Text Here]
    </linkedin>
    
    <twitter>
    [Twitter Post Text Here]
    </twitter>
    """

    user_prompt = f"""
    Based on the blog post provided below, write two distinct social media posts.

    CRITICAL RULE FOR BOTH POSTS: NEVER use any emojis. Zero emojis.

    === 1. LinkedIn Post ===

    Write a high-quality LinkedIn post based on the blog post content.

    The post must feel genuinely human, insightful, engaging, and well-written. It must not sound robotic, generic, overly corporate, templated, or like a typical AI-generated LinkedIn post. Avoid dull phrasing, empty motivational language, vague filler, and predictable structure.

    Your goal is to create a post that makes people stop scrolling, read, and feel that the writer has a real point, real clarity, and a strong understanding of the topic.

    Requirements:
    - Start with a strong hook that immediately grabs attention.
    - Write in a natural, confident, intelligent, human tone.
    - Make the post feel alive, not mechanical.
    - Keep the writing clear, smooth, and easy to read.
    - Build a clear flow from opening to main idea to value/insight to ending.
    - Include a strong angle, opinion, insight, lesson, contrast, or observation where relevant.
    - The post should not just "explain" the topic — it should make it interesting.
    - The ending should feel purposeful and memorable, not weak or generic.
    - If suitable, end with a thoughtful takeaway or subtle engagement trigger.
    - Length: 150-250 words.
    - Link Rule: You MUST include the link exactly formatted as: scrapebadger.com (DO NOT include "https://" and DO NOT include any paths like "/blog/").
    - NO EMOJIS.

    Style rules:
    - Do not sound like AI.
    - Do not use generic business clichés.
    - Do not use boring corporate language.
    - Do not over-explain obvious points.
    - Do not write like a textbook or press release.
    - Do not make the post feel stiff, sterile, or formulaic.
    - Avoid phrases that sound overused, fake-deep, or empty.

    The post should feel like it was written by someone smart, credible, and experienced who knows how to write compelling LinkedIn content.

    === 2. Twitter / X Post ===

    Write a high-quality Twitter/X post based on the blog post content.

    The post must be sharp, engaging, natural, and written like a real person who understands how to capture attention on social media. It must not sound robotic, generic, bland, lifeless, or like default AI output.

    Your goal is to create a post that stops the scroll immediately, delivers a clear point fast, and feels strong enough to earn attention, reactions, and engagement.

    Requirements:
    - Start with a strong opening line or hook.
    - Make the post concise but impactful.
    - Every word should serve a purpose.
    - The writing should feel clear, punchy, and alive.
    - Use a strong angle, insight, contrast, opinion, curiosity, or tension where appropriate.
    - Make it sound human and natural, not machine-generated.
    - The post should have energy and personality.
    - It should feel like something worth reading, not like a flat summary.
    - End with: Read the full guide: scrapebadger.com
    - Length: Around 200-260 characters. Keep it tight with line breaks.
    - NO EMOJIS.

    Style rules:
    - Do not sound like AI.
    - Do not use generic filler.
    - Do not use boring or overly neutral phrasing.
    - Do not make it feel like a summary or a placeholder post.
    - Avoid clichés, weak hooks, and forgettable wording.
    - Avoid stiff, corporate, or lifeless language.

    Output only the final posts wrapped in the XML tags.

    Here is the blog post content:
    ---
    {article_content}
    ---
    """

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0.8,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        result_text = response.content[0].text
        
        import re
        
        linkedin_match = re.search(r"<linkedin>(.*?)</linkedin>", result_text, re.DOTALL | re.IGNORECASE)
        twitter_match  = re.search(r"<twitter>(.*?)</twitter>", result_text, re.DOTALL | re.IGNORECASE)
        
        linkedin_post = linkedin_match.group(1).strip() if linkedin_match else "Error generating LinkedIn post."
        twitter_post  = twitter_match.group(1).strip() if twitter_match else "Error generating Twitter post."
        
        # Determine base path for the files
        base_name = os.path.splitext(file_path)[0]
        linkedin_file = f"{base_name}_linkedin.txt"
        twitter_file = f"{base_name}_twitter.txt"
        
        # Write LinkedIn
        with open(linkedin_file, "w", encoding="utf-8") as f:
            f.write(linkedin_post)
            
        # Write Twitter
        with open(twitter_file, "w", encoding="utf-8") as f:
            f.write(twitter_post)
            
        print("✨ --- GENERATED POSTS --- ✨")
        print(f"✅ LinkedIn post saved: {linkedin_file}")
        print(f"✅ Twitter post saved:  {twitter_file}")
        
    except Exception as e:
        print(f"⚠️ Error generating social posts: {e}")
        # Print raw output in case JSON failed completely
        try:
            print("\nClaude Output:")
            print(result_text)
        except:
            pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 execution/generate_social_posts.py \"article.md\"")
        sys.exit(1)
        
    article_path = sys.argv[1]
    api_key, model = get_config()
    
    generate_social_content(article_path, api_key, model)

if __name__ == "__main__":
    main()
