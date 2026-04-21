import os
import sys

print("Python version:", sys.version)

try:
    from google import genai
    print("google-genai import successful")
except Exception as e:
    print("google-genai import FAILED:", e)
    sys.exit(1)

def load_keys():
    keys = {}
    key_file = "anthropic_key.txt"
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys

keys = load_keys()
api_key = keys.get("GOOGLE_API_KEY")
if not api_key:
    print("GOOGLE_API_KEY not found in anthropic_key.txt")
    sys.exit(1)
else:
    print("GOOGLE_API_KEY found (length:", len(api_key), ")")

client = genai.Client(api_key=api_key)

model_names = ["gemini-1.5-flash", "gemini-1.5-flash-002", "gemini-2.0-flash-exp"]

for name in model_names:
    print(f"Testing {name}...")
    try:
        # Using a very simple prompt
        response = client.models.generate_content(model=name, contents="Hi")
        print(f"  ✅ SUCCESS: {name}")
    except Exception as e:
        print(f"  ❌ FAILED: {name} - {e}")
