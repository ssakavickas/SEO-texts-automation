import os
import sys
import requests

def get_telegram_config():
    """Fetches Telegram bot token and chat ID from environment or .env/anthropic_key.txt"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        try:
            # Check anthropic_key.txt first as convention
            with open("anthropic_key.txt", "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        bot_token = line.split("=", 1)[1].strip()
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        chat_id = line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
            
    if not bot_token or not chat_id:
        try:
            # Check .env as fallback
            if os.path.exists(".env"):
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith("TELEGRAM_BOT_TOKEN="):
                            bot_token = line.split("=", 1)[1].strip()
                        elif line.startswith("TELEGRAM_CHAT_ID="):
                            chat_id = line.split("=", 1)[1].strip()
        except Exception:
            pass
            
    return bot_token, chat_id

def send_message(bot_token, chat_id, text):
    """Sends a markdown-formatted message to a Telegram chat"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️ Error sending message to Telegram: {e}")
        return False
def send_document(bot_token, chat_id, file_path, caption=None):
    """Sends a document (file) to a Telegram chat"""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            if caption:
                data['caption'] = caption
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"⚠️ Error sending document to Telegram: {e}")
        return False

def send_photo(bot_token, chat_id, photo_path, caption=None):
    """Sends a photo to a Telegram chat"""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {'photo': f}
            data = {'chat_id': chat_id}
            if caption:
                data['caption'] = caption
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"⚠️ Error sending photo to Telegram: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 execution/send_to_telegram.py \"Topic Name\" \"path/to/blog.md\"")
        sys.exit(1)
        
    topic = sys.argv[1]
    md_file_path = sys.argv[2]
    
    bot_token, chat_id = get_telegram_config()
    
    if not bot_token or not chat_id:
        print("⚠️ Telegram configuration (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID) not found. Message will not be sent.")
        print("💡 Add them to your .env or anthropic_key.txt file.")
        sys.exit(0)
        
    base_name = os.path.splitext(md_file_path)[0]
    # If the file is CONSOLIDATED, the other assets (images, linkedin, etc) 
    # usually share the prefix BEFORE the _CONSOLIDATED part.
    if base_name.endswith("_CONSOLIDATED"):
        true_base = base_name.replace("_CONSOLIDATED", "")
    else:
        true_base = base_name
    
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    html_file = os.path.join(base_dir, f"{base_name}.html")
    cover_image = os.path.join(base_dir, f"{true_base}_cover.png")
    
    print(f"📱 Sending notification to Telegram...")
    
    # 1. Send the minimalist notification text first
    notification_text = f"🚀 <b>New blog post generated!</b>\nTopic: <i>{topic}</i>"
    send_message(bot_token, chat_id, notification_text)
    
    # 2. Send cover image as photo IMMEDIATELY after text
    if os.path.exists(cover_image):
        print(f"  📸 Sending cover image: {cover_image}")
        if send_photo(bot_token, chat_id, cover_image):
            print(f"  ✅ Sent cover photo")

    # 3. Send HTML file as document LAST
    is_consolidated = md_file_path.endswith("_CONSOLIDATED.md")
    if not os.path.isabs(md_file_path):
        md_file_abs = os.path.join(base_dir, md_file_path)
    else:
        md_file_abs = md_file_path

    if is_consolidated:
        current_html = md_file_abs.replace("_CONSOLIDATED.md", "_CONSOLIDATED.html")
    else:
        current_html = os.path.join(base_dir, f"{os.path.splitext(os.path.basename(md_file_path))[0]}.html")
 
    if os.path.exists(current_html):
        if send_document(bot_token, chat_id, current_html):
            print(f"  ✅ Sent file: {os.path.basename(current_html)}")
    else:
        print(f"  ⚠️ File not found: {current_html}")
                
    print("✅ All assets successfully sent to Telegram!")
    

if __name__ == "__main__":
    main()
