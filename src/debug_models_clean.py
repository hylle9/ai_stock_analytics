
import google.generativeai as genai
import os

# Try to find .env file
env_path = ".env"
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    api_key = line.strip().split("=")[1].strip().strip('"').strip("'")
                    break

if not api_key:
    print("NO API KEY FOUND in env or .env!")
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
