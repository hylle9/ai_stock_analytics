from src.data.ingestion import DataFetcher
import pandas as pd

def test_fetch():
    fetcher = DataFetcher()
    print(f"Provider: {type(fetcher.provider)}")
    
    ticker = "NVDA"
    print(f"Fetching {ticker}...")
    df = fetcher.fetch_ohlcv(ticker, period="1d")
    
    if df.empty:
        print("FAIL: DataFrame is empty")
    else:
        print(f"SUCCESS: Fetched {len(df)} rows")
        print(df.head())
        print(f"Last Close: {df['close'].iloc[-1]}")

if __name__ == "__main__":
    test_fetch()
