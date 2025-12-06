
import google.generativeai as genai
from src.utils.config import Config
import os

api_key = Config.GOOGLE_API_KEY
if not api_key:
    # Try fetching from env directly if Config fails
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("NO API KEY FOUND!")
else:
    print(f"API KEY FOUND: {api_key[:5]}...")
    genai.configure(api_key=api_key)
    try:
        print("Listing models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error listing models: {e}")
