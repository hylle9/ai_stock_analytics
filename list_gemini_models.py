import google.generativeai as genai
from src.utils.config import Config
import os

def list_models():
    api_key = Config.GOOGLE_API_KEY
    if not api_key:
        print("No GOOGLE_API_KEY found in .env")
        return

    genai.configure(api_key=api_key)
    print("Listing available models...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
