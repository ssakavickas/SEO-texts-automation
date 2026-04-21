import os
import sys
import markdown

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSS = """
<style>
    body { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
        line-height: 1.6; 
        max-width: 800px; 
        margin: 40px auto; 
        padding: 0 20px; 
        color: #333; 
    }
    h1, h2, h3 { 
        color: #111; 
        margin-top: 1.5em; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
        border-bottom: 2px solid #2D6A4F;
        padding-bottom: 5px;
    }
    pre { 
        background-color: #1e1e1e; 
        color: #d4d4d4; 
        padding: 16px; 
        border-radius: 6px; 
        overflow-x: auto; 
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; 
        font-size: 14px; 
        margin: 20px 0;
    }
    code { 
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; 
    }
    p code {
        background-color: #f6f8fa; 
        padding: 0.2em 0.4em; 
        border-radius: 3px; 
        font-size: 85%;
        color: #2D6A4F;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 20px 0;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 12px;
        text-align: left;
    }
    th {
        background-color: #f8f9fa;
    }
</style>
"""

def convert_md_to_html(md_path, html_path=None):
    """Converts a markdown file to HTML. Returns the path to the created HTML file."""
    if not os.path.isabs(md_path):
        md_path = os.path.join(os.getcwd(), md_path)

    if not os.path.exists(md_path):
        print(f"Markdown file not found: {md_path}")
        return None

    if not html_path:
        html_path = os.path.splitext(md_path)[0] + ".html"

    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Convert markdown to HTML including fenced code blocks, tables, and attributes
    html_content = markdown.markdown(text, extensions=['fenced_code', 'tables', 'attr_list'])
    
    # Extract a title from the H1 or filename
    title_match = markdown.markdown(text.split('\n')[0]).replace('<h1>','').replace('</h1>','')
    title = title_match if title_match else os.path.basename(md_path)

    # Wrap in full HTML document
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>{title}</title>
    {CSS}
</head>
<body>
    {html_content}
</body>
</html>"""
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
        
    print(f"Success! Created {html_path}")
    return html_path

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 export_to_html.py <path_to_markdown_file>")
        return

    md_path = sys.argv[1]
    convert_md_to_html(md_path)

if __name__ == "__main__":
    main()
