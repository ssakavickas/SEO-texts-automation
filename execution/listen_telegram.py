import os
import sys
import time
import json
import re
import traceback
import subprocess
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")

def get_telegram_config():
    """Fetches Telegram bot token from environment or .env/anthropic_key.txt"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        try:
            with open(os.path.join(BASE_DIR, "anthropic_key.txt"), "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        bot_token = line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
            
    if not bot_token:
        try:
            with open(os.path.join(BASE_DIR, ".env"), "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        bot_token = line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
            
    return bot_token

def send_message(bot_token, chat_id, text):
    """Sends a message back to the Telegram chat"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

def parse_blog_command(text):
    """
    Parses a message looking for:
    /blog
    Topic: [topic]
    Primary Keyword: [keyword]
    Secondary Keywords: [keywords]
    Word Count: [optional number]
    
    Supports both multi-line and single-line formats.
    """
    text = text.strip()
    if not text.lower().startswith('/blog'):
        return None
        
    data = {
        "topic": "Automated Blog Topic",
        "primary_keyword": "blog",
        "secondary_keywords": "",
        "word_count": 2000
    }
    
    # Try to extract topic
    topic_match = re.search(r'(?i)topic:\s*(.+?)(?=\n|primary keyword:|secondary keywords:|word count:|$)', text)
    if topic_match:
        data["topic"] = topic_match.group(1).strip()
    elif len(text.split('\n')[0].strip()) > 6:
        # If /blog is followed by text on same line and no "Topic:" found
        # e.g. "/blog Python Tutorial"
        first_line = text.split('\n')[0]
        data["topic"] = first_line.replace('/blog', '', 1).strip()
        if not data["topic"]:
            data["topic"] = "Automated Blog Topic"

    # Keywords extraction
    pk_match = re.search(r'(?i)primary keyword:\s*(.+?)(?=\n|topic:|secondary keywords:|word count:|$)', text)
    if pk_match:
        data["primary_keyword"] = pk_match.group(1).strip()
        
    sk_match = re.search(r'(?i)secondary keywords:\s*(.+?)(?=\n|topic:|primary keyword:|word count:|$)', text)
    if sk_match:
        data["secondary_keywords"] = sk_match.group(1).strip()
        
    wc_match = re.search(r'(?i)word count:\s*(\d+)', text)
    if wc_match:
        data["word_count"] = int(wc_match.group(1))
                
    return data

def run_pipeline(chat_id, bot_token):
    """Triggers the pipeline script"""
    send_message(bot_token, chat_id, "⏳ <b>New request received!</b> Starting blog generation (this may take a few minutes)...")
    
    try:
        pipeline_path = os.path.join(BASE_DIR, "execution", "pipeline.py")
        print(f"Executing: python3 {pipeline_path}")
        
        # We run it sequentially. send_to_telegram handles the final success message.
        process = subprocess.run(
            [sys.executable, pipeline_path],
            capture_output=True,
            text=True,
            check=True
        )
        print("Pipeline finished successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"Pipeline error: {e}")
        error_msg = f"❌ <b>Error generating blog:</b>\n<pre>{e.stderr[-500:] if e.stderr else 'Unknown error'}</pre>"
        send_message(bot_token, chat_id, error_msg)
    except Exception as e:
        print(f"System error: {e}")
        send_message(bot_token, chat_id, f"❌ <b>System error:</b> {str(e)}")
    finally:
        # Cleanup the override file
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            print(f"Cleaned up {OUTPUT_FILE}")

def main():
    bot_token = get_telegram_config()
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found!")
        sys.exit(1)
        
    print("🤖 Telegram listener started. Waiting for new commands...")
    
    offset = None
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    # Ensure tmp dir exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
                
            response = requests.get(url, params=params, timeout=35)
            # Skip on non-200 just in case connection is flaky
            if not response.ok:
                time.sleep(2)
                continue
                
            data = response.json()
            
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                
                if "message" not in update or "text" not in update["message"]:
                    continue
                    
                message_text = update["message"]["text"]
                chat_id = update["message"]["chat"]["id"]
                
                if message_text.startswith("/blog"):
                    print(f"\n[+] Accepted command /blog from chat_id: {chat_id}")
                    
                    parsed_inputs = parse_blog_command(message_text)
                    if parsed_inputs:
                        # Save inputs for agents to read
                        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                            json.dump(parsed_inputs, f, indent=2)
                        print(f"  Inputs saved: {parsed_inputs['topic']}")
                        
                        # Trigger pipeline
                        run_pipeline(chat_id, bot_token)
                    else:
                        help_text = (
                            "❌ Invalid format. Example:\n\n"
                            "/blog\n"
                            "Topic: How to program Python\n"
                            "Primary Keyword: python programming\n"
                            "Secondary Keywords: code, tutorial\n"
                            "Word Count: 1000"
                        )
                        send_message(bot_token, chat_id, help_text)
                elif message_text.startswith("/repair"):
                    print(f"\n[+] Accepted command /repair from chat_id: {chat_id}")
                    feedback = message_text.replace("/repair", "").strip()
                    if feedback:
                        feedback_file = os.path.join(BASE_DIR, ".tmp", "repair_feedback.txt")
                        with open(feedback_file, "w", encoding="utf-8") as f:
                            f.write(feedback)
                        
                        send_message(bot_token, chat_id, f"📝 <b>Repair request received:</b>\n<i>{feedback}</i>\nRegenerating package...")
                        
                        # Run pipeline with repair flag
                        try:
                            pipeline_path = os.path.join(BASE_DIR, "execution", "pipeline.py")
                            subprocess.run([sys.executable, pipeline_path, "--repair"], check=True)
                        except Exception as e:
                            send_message(bot_token, chat_id, f"❌ Error during repair: {e}")
                    else:
                        send_message(bot_token, chat_id, "❌ Please specify what you want to fix. Example: <code>/repair Change the intro to be more provocative</code>")
                elif message_text.startswith("/ping"):
                    send_message(bot_token, chat_id, "🏓 Pong! I'm alive and listening to your commands.")
                    
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()
