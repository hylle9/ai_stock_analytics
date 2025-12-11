import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.getcwd())

from src.data.ingestion import DataFetcher
from src.utils.config import Config

def test_fetch():
    print(f"Config Strategy: {Config.DATA_STRATEGY}")
    print(f"Synthetic DB: {Config.USE_SYNTHETIC_DB}")
    
    fetcher = DataFetcher()
    
    tickers = ["AAPL", "MSFT"]
    
    for t in tickers:
        print(f"\n--- Testing {t} ---")
        try:
            # Force valid period
            df = fetcher.fetch_ohlcv(t, period="1y", use_cache=False)
            print(f"Shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()}")
            if not df.empty:
                print(df.head(2))
            else:
                print("DataFrame is EMPTY")
        except Exception as e:
            print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    test_fetch()
