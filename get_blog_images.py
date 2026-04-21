import requests
from bs4 import BeautifulSoup

def get_images():
    url = "https://scrapebadger.com/blog"
    # Basic Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        images = soup.find_all("img")

        for img in images:
            src = img.get("src")
            alt = img.get("alt", "")
            if src and not src.endswith(".svg"):
                # Handle relative URLs
                if src.startswith("/"):
                    src = "https://scrapebadger.com" + src
                print(f"Image: {src} | Alt: {alt}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_images()
