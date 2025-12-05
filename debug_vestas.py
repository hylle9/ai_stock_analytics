from src.data.ingestion import DataFetcher
import pandas as pd

def test_vestas():
    fetcher = DataFetcher()
    ticker = "VWSA.FRK"
    print(f"Attempting to fetch {ticker}...")
    
    # Try fetching
    try:
        df = fetcher.fetch_ohlcv(ticker, period="1y")
        print(f"Fetch Result Type: {type(df)}")
        if df.empty:
            print("DATAFRAME IS EMPTY")
        else:
            print(f"Data Found: {len(df)} rows")
            print(df.head())
    except Exception as e:
        print(f"Exception during fetch: {e}")

    # Also try the known Copenhagen ticker for comparison if above fails
    ticker_co = "VWS.CO"
    print(f"\nAttempting to fetch {ticker_co} (Copenhagen)...")
    try:
        df = fetcher.fetch_ohlcv(ticker_co, period="1y")
        if df.empty:
            print("DATAFRAME IS EMPTY")
        else:
            print(f"Data Found: {len(df)} rows")
    except Exception as e:
        print(f"Exception during fetch: {e}")

if __name__ == "__main__":
    test_vestas()
