import os
from google import genai

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
api_key = keys.get("GOOGLE_API_KEY")

with open("model_list.txt", "w") as f:
    f.write(f"Testing with API Key length: {len(api_key) if api_key else 'None'}\n")
    try:
        client = genai.Client(api_key=api_key)
        f.write("Client initialized\n")
        models = client.models.list()
        f.write("Listing models:\n")
        for m in models:
            f.write(f"{m.name}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
