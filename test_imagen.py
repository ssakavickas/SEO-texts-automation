from google import genai
from google.genai import types

key = "AIzaSyCk3S1W5x0vkDHM8iQTcAEb2jpkHMYq8OY"
client = genai.Client(api_key=key)

try:
    result = client.models.generate_images(
        model='imagen-3.0-generate-001',
        prompt='A simple red apple',
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1"
        )
    )
    if result.generated_images:
        print("IMAGEN 001 SUCCESS")
except Exception as e:
    print(f"IMAGEN 001 ERROR: {e}")
