import os
import sys

def consolidate(md_path):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_name = os.path.splitext(md_path)[0]
    consolidated_path = f"{base_name}_CONSOLIDATED.md"
    
    linkedin_path = f"{base_name}_linkedin.txt"
    twitter_path = f"{base_name}_twitter.txt"
    seo_path = f"{base_name}_seo_meta.txt"
    cover_path = f"{base_name}_cover.png"
    
    content = ""

    
    # SEO Section
    if os.path.exists(seo_path):
        content += "## SEO Metadata\n"
        with open(seo_path, "r") as f:
            content += f.read()
        content += "\n\n---\n\n"
        
    # LinkedIn Section
    if os.path.exists(linkedin_path):
        content += "## LinkedIn Post\n"
        with open(linkedin_path, "r") as f:
            content += f.read()
        content += "\n\n---\n\n"
        
    # Twitter Section
    if os.path.exists(twitter_path):
        content += "## Twitter Thread\n"
        with open(twitter_path, "r") as f:
            content += f.read()
        content += "\n\n---\n\n"
        
    # Cover Image
    if os.path.exists(cover_path):
        content += "## Blog Cover Image\n"
        content += f"![Cover Image]({cover_path})\n\n---\n\n"
        
    # Main Blog
    if os.path.exists(md_path):
        with open(md_path, "r") as f:
            blog_text = f.read()
            # If the first line is the title as # Title, we keep it. 
            content += blog_text
            
    with open(consolidated_path, "w") as f:
        f.write(content)
        
    print(f"✅ Consolidated file created: {consolidated_path}")
    return consolidated_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        consolidate(sys.argv[1])
