import sys
import os
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.getcwd())

from src.utils.config import Config
from src.data.ingestion import DataFetcher

def verify_providers():
    print("=== Verifying Data Providers ===")
    
    # Check Config
    print(f"API Key Present: {bool(Config.ALPHA_VANTAGE_API_KEY)}")
    print(f"Cache Dir: {Config.DATA_CACHE_DIR}")
    
    fetcher = DataFetcher()
    
    # 1. Test OHLCV
    print("\n--- Testing OHLCV (AAPL) ---")
    df = fetcher.fetch_ohlcv("AAPL", period="1mo")
    if not df.empty:
        print(f"Success! Fetched {len(df)} rows.")
        print(df.head(2))
    else:
        print("Failed to fetch OHLCV (likely due to missing API key or limit).")

    # 2. Test News
    print("\n--- Testing News (AAPL) ---")
    news = fetcher.fetch_news("AAPL")
    if news:
        print(f"Success! Fetched {len(news)} articles.")
        print(f"Sample: {news[0]['title']}")
    else:
        print("No news fetched.")

    # 3. Test Alt Data (Sentiment & Attention)
    print("\n--- Testing Alt Data (Sentiment & Attention) ---")
    alt_df = fetcher.fetch_alt_data("AAPL", days=5)
    print(alt_df.head())
    print("Social_Sentiment stats:", alt_df['Social_Sentiment'].describe())
    print("Web_Attention stats:", alt_df['Web_Attention'].describe())
    
    # Check if attention is real number (0-100) and not just 0 (if API failed it might be 0)
    # But note: StockTwits might return 0 if no msgs.
    if alt_df['Web_Attention'].mean() > 0:
        print("Success! Web Attention > 0 (Real Data)")
    else:
        print("Warning: Web Attention is 0. Check StockTwits API or Ticker.")

if __name__ == "__main__":
    verify_providers()
