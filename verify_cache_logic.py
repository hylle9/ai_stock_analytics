from src.analytics.insights import InsightManager
from datetime import datetime

def verify():
    print(f"Current System Date: {datetime.now().strftime('%Y-%m-%d')}")
    
    im = InsightManager()
    print(f"Cache keys in memory: {list(im.cache.keys())}")
    
    ticker = "GOOG"
    insight = im.get_todays_insight(ticker)
    
    if insight:
        print(f"[SUCCESS] Found cached insight for {ticker}:")
        print(insight[:100] + "...")
    else:
        print(f"[FAILURE] Could not find cached insight for {ticker} (Date mismatch or missing).")
        if ticker in im.cache:
            print(f"Entry in cache: {im.cache[ticker]}")

if __name__ == "__main__":
    verify()
