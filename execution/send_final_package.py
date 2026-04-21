import os
import sys
import requests

def get_telegram_config():
    bot_token = None
    chat_id = None
    try:
        with open("anthropic_key.txt", "r") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    bot_token = line.split("=", 1)[1].strip()
                elif line.startswith("TELEGRAM_CHAT_ID="):
                    chat_id = line.split("=", 1)[1].strip()
    except Exception as e:
        print(f"Error reading keys: {e}")
    return bot_token, chat_id

def send_file(bot_token, chat_id, file_path, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {'chat_id': chat_id, 'caption': caption}
    try:
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        print(f"✅ File {os.path.basename(file_path)} sent!")
    except Exception as e:
        print(f"❌ Error sending file: {e}")

def main():
    html_file = "twitter_competitor_tracking_blog_CONSOLIDATED.html"
    cover_image = "twitter_competitor_tracking_blog_cover.png" # Optional but good to have
    
    bot_token, chat_id = get_telegram_config()
    
    if not bot_token or not chat_id:
        print("❌ Telegram configuration not found.")
        return

    # Send HTML
    if os.path.exists(html_file):
        send_file(bot_token, chat_id, html_file, "📄 Final Blog (HTML format)")
    else:
        print(f"❌ {html_file} not found")

    # Send Cover as well since it's part of the project
    if os.path.exists(cover_image):
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        with open(cover_image, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': chat_id, 'caption': '🎨 Blog Cover'}
            requests.post(url, files=files, data=data)
            print("✅ Cover sent!")

if __name__ == "__main__":
    main()
