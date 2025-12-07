from src.data.ingestion import DataFetcher
from src.utils.config import Config
import sys

# Force Synthetic Mode
Config.USE_SYNTHETIC_DB = True
print(f"Configuring Synthetic Mode: {Config.USE_SYNTHETIC_DB}")
print(f"API Key Present: {bool(Config.ALPHA_VANTAGE_API_KEY)}")

fetcher = DataFetcher()
print("Attempting to fetch GOOGL...")
df = fetcher.fetch_ohlcv("GOOGL")

if not df.empty:
    print(f"✅ Success! Fetched {len(df)} rows.")
    print(df.head())
else:
    print("❌ Failure! Returned empty DataFrame.")
