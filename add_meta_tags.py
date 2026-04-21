import re
import json

def update_html():
    # Read Markdown for frontmatter
    with open("twitter_competitor_tracking_blog.md", "r") as f:
        md_content = f.read()
        
    frontmatter_match = re.search(r"^---\n(.*?)\n---", md_content, re.DOTALL)
    if not frontmatter_match: return
    
    # Extract
    title_match = re.search(r'meta_title:\s*"(.*?)"', frontmatter_match.group(1))
    desc_match = re.search(r'meta_description:\s*"(.*?)"', frontmatter_match.group(1))
    
    if not title_match or not desc_match: return
    
    meta_title = title_match.group(1)
    meta_desc = desc_match.group(1)
    
    # Update HTML
    with open("twitter_competitor_tracking_blog.html", "r") as f:
        html_content = f.read()
        
    # Replace existing title if any, or add it
    if "<title>" in html_content:
        html_content = re.sub(r"<title>.*?</title>", f"<title>{meta_title}</title>", html_content)
    elif "<head>" in html_content:
        html_content = html_content.replace("<head>", f"<head>\n    <title>{meta_title}</title>")
        
    # Replace existing meta description if any, or add it
    if "name=\"description\"" in html_content:
        html_content = re.sub(r'<meta name="description" content=".*?">', f'<meta name="description" content="{meta_desc}">', html_content)
    elif "<head>" in html_content:
        html_content = html_content.replace("<head>", f"<head>\n    <meta name=\"description\" content=\"{meta_desc}\">")
        
    # If no head, wrap it
    if "<head>" not in html_content:
        html_content = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>{meta_title}</title>\n    <meta name=\"description\" content=\"{meta_desc}\">\n</head>\n<body>\n{html_content}\n</body>\n</html>"

    with open("twitter_competitor_tracking_blog.html", "w") as f:
        f.write(html_content)

update_html()
