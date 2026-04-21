import requests
from bs4 import BeautifulSoup
import re
import os

def main():
    sitemap_url = "https://scrapebadger.com/sitemap.xml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(sitemap_url, headers=headers)
    soup = BeautifulSoup(response.text, "xml")
    
    os.makedirs(".tmp/all_references", exist_ok=True)
    count = 0
    
    print("Scraping all blog post images...")
    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        if re.match(r"https://scrapebadger\.com/blog/.+", url):
            try:
                print(f"Checking {url}")
                post_html = requests.get(url, headers=headers).text
                post_soup = BeautifulSoup(post_html, "html.parser")
                
                # Check for og:image
                og_image = post_soup.find("meta", property="og:image")
                if og_image and og_image.get("content"):
                    img_url = og_image["content"]
                    filename = f".tmp/all_references/ref_{count}.jpg"
                    
                    img_response = requests.get(img_url, stream=True)
                    if img_response.status_code == 200:
                        with open(filename, 'wb') as f:
                            for chunk in img_response.iter_content(8192):
                                f.write(chunk)
                        print(f"  -> Saved {filename}")
                        count += 1
            except Exception as e:
                print(f"  -> Error: {e}")
                
    print(f"Total reference images downloaded: {count}")

if __name__ == "__main__":
    main()
