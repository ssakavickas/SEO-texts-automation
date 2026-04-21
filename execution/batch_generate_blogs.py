import os
import json
import subprocess
import time
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "execution"))

INPUT_FILE = os.path.join(BASE_DIR, ".tmp", "blog_inputs.json")
PIPELINE_PATH = os.path.join(BASE_DIR, "execution", "pipeline.py")

TOPICS = [
    "How to Build a Real-Time Twitter Monitoring Pipeline",
    "How Startups Use Twitter Monitoring for Lead Generation",
    "Twitter Monitoring vs Twitter Scraping: What’s the Difference?",
    "How to Detect Viral Trends Early Using Twitter Streams",
    "10 Twitter Monitoring Strategies for B2B SaaS"
]

def run_batch():
    consolidated_files = []
    cover_images = []
    
    for i, topic in enumerate(TOPICS):
        print(f"\n🚀 Starting Generation {i+1}/5: {topic}")
        
        data = {
            "topic": topic,
            "primary_keyword": topic.lower(),
            "secondary_keywords": "twitter monitoring, scrapebadger, twitter scraping, lead generation",
            "word_count": 1500
        }
        
        os.makedirs(os.path.dirname(INPUT_FILE), exist_ok=True)
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        try:
            # Run pipeline with --no-telegram
            subprocess.run([sys.executable, "-u", PIPELINE_PATH, "--no-telegram"], check=True)
            
            # Identify the consolidated file path
            # Topic to filename conversion (usually lowercase, underscores)
            fname_base = topic.lower().replace(" ", "_").replace(":", "").replace("?", "").replace("'", "").replace("(","").replace(")","")
            if len(fname_base) > 50: fname_base = fname_base[:50]
            if fname_base.endswith("_"): fname_base = fname_base[:-1]
            
            # Correct path detection logic
            # The pipeline saves the main file as [fname_base]_blog.md
            # And consolidation creates [fname_base]_blog_CONSOLIDATED.md
            # Let's check for the actual file
            potential_file = os.path.join(BASE_DIR, f"{fname_base}_blog_CONSOLIDATED.md")
            if os.path.exists(potential_file):
                consolidated_files.append((topic, potential_file))
                print(f"✅ Collected: {os.path.basename(potential_file)}")
            else:
                # Fallback: list files and find by prefix
                import glob
                matches = glob.glob(os.path.join(BASE_DIR, f"{fname_base}*_CONSOLIDATED.md"))
                if matches:
                    consolidated_files.append((topic, matches[0]))
                    print(f"✅ Collected (glob): {os.path.basename(matches[0])}")
            
            # Collect cover image
            cover_path = os.path.join(BASE_DIR, f"{fname_base}_blog_cover.png")
            if os.path.exists(cover_path):
                cover_images.append(cover_path)
                print(f"🖼️  Collected cover: {os.path.basename(cover_path)}")
                    
            print(f"✅ Finished Generation {i+1}/5")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error in Generation {i+1}: {e}")
            
        time.sleep(2)

    # FINAL STEP: Merge all files
    if consolidated_files:
        print("\n📦 Merging all results into a single MASTER package...")
        master_file_path = os.path.join(BASE_DIR, "MASTER_BLOG_BATCH_PACKAGE.md")
        
        with open(master_file_path, "w", encoding="utf-8") as master:
            master.write("# 📦 ScrapeBadger Content Batch Package\n\n")
            master.write(f"Total Articles: {len(consolidated_files)}\n")
            master.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            master.write("---\n\n")
            
            for topic, f_path in consolidated_files:
                master.write(f"## 📄 {topic}\n\n")
                with open(f_path, "r", encoding="utf-8") as f:
                    master.write(f.read())
                master.write("\n\n---\n\n")

        print(f"✅ Master file created: {master_file_path}")
        
        # Create Master HTML
        import export_to_html
        master_html_path = master_file_path.replace(".md", ".html")
        export_to_html.convert_md_to_html(master_file_path, master_html_path)
        print(f"✅ Master HTML created: {master_html_path}")

        # Send to Telegram
        print("📱 Sending Master Package to Telegram...")
        from send_to_telegram import send_message, send_document, send_photo
        # Get keys for notification
        from generate_blog_images_google import load_keys
        keys = load_keys()
        bot_token = keys.get("TELEGRAM_BOT_TOKEN")
        chat_id = keys.get("TELEGRAM_CHAT_ID")
        
        if bot_token and chat_id:
            msg = f"✅ <b>Batch complete!</b>\nGenerated all {len(consolidated_files)} articles into a single file.\nImages are being sent separately."
            send_message(bot_token, chat_id, msg)
            
            # Send the master files
            send_document(bot_token, chat_id, master_file_path)
            send_document(bot_token, chat_id, master_html_path)
            
            # Send each cover image separately
            for img_path in cover_images:
                if os.path.exists(img_path):
                    send_photo(bot_token, chat_id, img_path, caption=f'🎨 Cover: {os.path.basename(img_path)}')
                    print(f"🖼️  Sent photo: {os.path.basename(img_path)}")
            
            print("🚀 Master package and photos delivered to Telegram!")
        else:
            print("❌ Missing Telegram credentials for final delivery.")

if __name__ == "__main__":
    run_batch()
