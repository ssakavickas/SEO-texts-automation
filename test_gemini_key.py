from google import genai
client = genai.Client(api_key="AIzaSyCk3S1W5x0vkDHM8iQTcAEb2jpkHMYq8OY")
try:
    response = client.models.generate_content(model='gemini-2.5-flash', contents='Hi')
    print("Gemini Flash SUCCESS, response:", response.text)
except Exception as e:
    print(f"Gemini Flash ERROR: {e}")
