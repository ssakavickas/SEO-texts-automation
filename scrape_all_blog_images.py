import requests
from bs4 import BeautifulSoup
import re
import os

def download_image(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        print(f"Downloaded: {filename}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def main():
    sitemap_url = "https://scrapebadger.com/sitemap.xml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(sitemap_url, headers=headers)
    soup = BeautifulSoup(response.text, "xml")
    
    os.makedirs(".tmp/reference_images", exist_ok=True)
    count = 0
    
    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        if re.match(r"https://scrapebadger\.com/blog/.+", url):
            try:
                post_html = requests.get(url, headers=headers).text
                post_soup = BeautifulSoup(post_html, "html.parser")
                
                # Check for og:image
                og_image = post_soup.find("meta", property="og:image")
                if og_image and og_image.get("content"):
                    img_url = og_image["content"]
                    filename = f".tmp/reference_images/ref_{count}.jpg"
                    if download_image(img_url, filename):
                        count += 1
                        if count >= 3: # Let's get up to 3 for max generation context
                            break
            except Exception as e:
                pass
                
if __name__ == "__main__":
    main()
