"""
execution/generate_seo_meta.py

Šis skriptas perskaito nurodytą blogo straipsnį ir, naudodamas Claude AI, 
sugeneruoja jam tobulai SEO optimizuotą "Meta Title" bei "Meta Description".

Naudojimas:
python3 execution/generate_seo_meta.py "kelias/iki/blogo_failo.md"
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

def generate_seo_metadata(file_path: str, api_key: str, model: str, keyword: str = None):
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        article_content = f.read()

    print(f"📄 Reading article: {file_path} ({len(article_content)} characters)")
    if keyword:
        print(f"🔑 Using provided Primary Keyword: {keyword}")
    print(f"🤖 Calling Claude ({model}) for SEO metadata generation...\n")

    client = Anthropic(api_key=api_key)

    if keyword:
        system_prompt = f"""
    Your task is to create a strictly SEO-optimized meta title and meta description based on the blog post provided by the user.
    The primary keyword is: "{keyword}" — you MUST use this exact keyword. Do NOT invent or substitute a different keyword.
    Ensure the title and description accurately represent the article content.
    Optimize for Google search results (SERP CTR).

    OUTPUT FORMAT:
    Return ONLY a JSON object (no markdown formatting, no explanations) exactly like this:
    {{
        "PrimaryKeyword": "{keyword}",
        "MetaTitle": "The 50-60 character title",
        "MetaDescription": "The 140-160 character description"
    }}
    """
    else:
        system_prompt = """
    Your task is to create a strictly SEO-optimized meta title and meta description based on the blog post provided by the user.
    Identify the primary keyword from the article automatically.
    Ensure the title and description accurately represent the article content.
    Optimize for Google search results (SERP CTR).

    OUTPUT FORMAT:
    Return ONLY a JSON object (no markdown formatting, no explanations) exactly like this:
    {
        "PrimaryKeyword": "the keyword",
        "MetaTitle": "The 50-60 character title",
        "MetaDescription": "The 140-160 character description"
    }
    """

    keyword_instruction = f"\n    Primary Keyword: {keyword}\n    You MUST use this exact keyword in both the meta title and meta description.\n" if keyword else ""

    user_prompt = f"""
    Follow these SEO best practices exactly:
    {keyword_instruction}
    Meta Title Requirements
    • Length: 50–60 characters
    • Include the primary keyword naturally
    • Make it clear, compelling, and clickable
    • Reflect the main intent of the article
    • Avoid keyword stuffing
    • Use title case
    • Do not use quotation marks

    Meta Description Requirements
    • Length: 140–160 characters
    • Summarize the main value of the article
    • Include the primary keyword naturally
    • Make it engaging and click-worthy
    • Add a subtle call-to-action when appropriate
    • Avoid duplication of the title
    • Write in natural, human language

    Here is the blog post content:
    ---
    {article_content}
    ---
    """

    response = client.messages.create(
        model=model,
        max_tokens=500,
        temperature=0.3, # Low temp for precision and adherence to character limits
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )

    result_text = response.content[0].text
    
    # Print the raw, structured result
    print("✨ --- SUGENERUOTI SEO DUOMENYS --- ✨")
    print(result_text)
    print("✨ -------------------------------- ✨")

    import json
    try:
        # Extract json. Claude might wrap it in ```json``` blocks
        json_str = result_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
            
        seo_data = json.loads(json_str)
        
        # Save as a separate file
        base_name = os.path.splitext(file_path)[0]
        output_txt = f"{base_name}_seo_meta.txt"
        
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(f"Primary Keyword: {seo_data.get('PrimaryKeyword', '')}\n")
            f.write(f"Meta Title: {seo_data.get('MetaTitle', '')}\n")
            f.write(f"Meta Description: {seo_data.get('MetaDescription', '')}\n")
            
        print(f"✅ SEO Meta data saved separately to file: {output_txt}")
        
    except Exception as e:
        print(f"⚠️ Could not automatically save data to file: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 execution/generate_seo_meta.py \"article.md\"")
        sys.exit(1)
        
    article_path = sys.argv[1]
    keyword = sys.argv[2] if len(sys.argv) > 2 else None
    api_key, model = get_config()

    generate_seo_metadata(article_path, api_key, model, keyword=keyword)

if __name__ == "__main__":
    main()
