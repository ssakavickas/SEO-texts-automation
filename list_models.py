import os
import google.genai as genai

def load_keys():
    keys = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    key_file = os.path.join(base_dir, "anthropic_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys

keys = load_keys()
client = genai.Client(api_key=keys.get("GOOGLE_API_KEY"))

print("Listing models...")
try:
    for model in client.models.list():
        print(f"Model: {model.name}, Methods: {model.supported_methods}")
except Exception as e:
    print(f"Error: {e}")
