from src.data.ingestion import DataFetcher
import json

try:
    fetcher = DataFetcher()
    print("Fetching news for MSFT...")
    news = fetcher.fetch_news("MSFT")
    
    if news:
        print(f"Successfully fetched {len(news)} news items for MSFT.")
        print("First item sample:")
        print(json.dumps(news[0], indent=2))
        
        # Verify structure
        item = news[0]
        if 'title' in item and 'link' in item:
             print("\nSUCCESS: MSFT news structure is valid.")
        else:
             print("\nFAILURE: MSFT news missing keys.")
    else:
        print("No news found for MSFT.")

except Exception as e:
    print(f"Error fetching MSFT news: {e}")
