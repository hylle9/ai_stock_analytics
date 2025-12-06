import pandas as pd
import os
import numpy as np
from datetime import datetime
from src.utils.config import Config
from src.data.providers import AlphaVantageProvider, BaseDataProvider, YFinanceProvider

class DataFetcher:
    """
    Fetches market data using configured providers.
    Wrapper around BaseDataProvider with caching layer.
    """
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or Config.DATA_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize Provider
        av_key = Config.ALPHA_VANTAGE_API_KEY
        # Check against common placeholders
        if av_key and "your_" not in av_key.lower() and len(av_key) > 5:
             self.provider: BaseDataProvider = AlphaVantageProvider()
        else:
             print("Warning: No valid Alpha Vantage API key found. Using YFinance fallback.")
             self.provider: BaseDataProvider = YFinanceProvider()

    def _get_cache_path(self, ticker: str, period: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_{period}.parquet")

    def fetch_ohlcv(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch daily OHLCV data.
        """
        cache_path = self._get_cache_path(ticker, period)
        
        # Try cache first
        if use_cache and os.path.exists(cache_path):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if mtime.date() == datetime.now().date():
                    print(f"Loading {ticker} from cache...")
                    return pd.read_parquet(cache_path)
            except Exception as e:
                print(f"Error reading cache for {ticker}: {e}")

        # Fetch from Provider
        print(f"Fetching {ticker} from Provider...")
        df = pd.DataFrame()
        try:
            df = self.provider.fetch_ohlcv(ticker, period)
        except Exception as e:
            print(f"Error downloading {ticker}: {e}")
        
        # Runtime Fallback: If primary failed/empty and we aren't already using YFinance
        if df.empty and not isinstance(self.provider, YFinanceProvider):
            print(f"Primary provider returned no data for {ticker}. Attempting fallback to YFinance...")
            try:
                fallback = YFinanceProvider()
                df = fallback.fetch_ohlcv(ticker, period)
            except Exception as e:
                print(f"Fallback fetch failed: {e}")

        if df.empty:
            print(f"Warning: No data found for {ticker}")
            return pd.DataFrame()
            
        # Standardize columns just in case
        required_cols = ["open", "high", "low", "close", "volume"]
        # Ensure lowercase
        df.columns = [c.lower() for c in df.columns]
        
        # Save to cache
        if not df.empty:
            try:
                df.to_parquet(cache_path)
            except Exception as e:
                print(f"Error saving cache for {ticker}: {e}")
                
        return df

    
    def _get_news_cache_path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_news.json")

    def fetch_news(self, ticker: str, limit: int = 50) -> list:
        """
        Fetch news headlines with caching (3-day retention, daily merge).
        """
        import json
        cache_path = self._get_news_cache_path(ticker)
        now_ts = int(datetime.now().timestamp())
        retention_window = 3 * 24 * 3600 # 3 days in seconds
        
        cached_news = []
        cache_is_fresh = False
        
        # 1. Load Cache
        if os.path.exists(cache_path):
            try:
                # Check freshness (Daily resolution)
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if mtime.date() == datetime.now().date():
                    cache_is_fresh = True
                
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Filter old items immediately
                        cached_news = [
                            item for item in data 
                            if item.get('providerPublishTime', 0) > (now_ts - retention_window)
                        ]
            except Exception as e:
                print(f"Error reading news cache for {ticker}: {e}")
        
        # 2. Return Cache if Fresh
        if cache_is_fresh and cached_news:
            # Sort just in case
            cached_news.sort(key=lambda x: x.get('providerPublishTime', 0), reverse=True)
            return cached_news
            
        # 3. Fetch New Data (if stale or empty)
        print(f"News cache stale or empty for {ticker}. Fetching new articles...")
        new_news = []
        try:
            new_news = self.provider.fetch_news(ticker, limit=limit)
        except Exception as e:
             print(f"Error fetching new news: {e}")
        
        # 4. Merge Strategies
        # Combine lists
        combined = new_news + cached_news
        
        # Deduplicate by Link (primary) or Title (secondary)
        seen_links = set()
        unique_news = []
        
        for item in combined:
            link = item.get('link')
            title = item.get('title')
            
            # Create a unique key
            key = link if link and link != '#' else title
            
            if key and key not in seen_links:
                seen_links.add(key)
                # Keep if within retention window
                if item.get('providerPublishTime', 0) > (now_ts - retention_window):
                    unique_news.append(item)
        
        # Sort DESC
        unique_news.sort(key=lambda x: x.get('providerPublishTime', 0), reverse=True)
        
        # 5. Save Cache
        try:
            with open(cache_path, 'w') as f:
                json.dump(unique_news, f, indent=2)
        except Exception as e:
            print(f"Error saving news cache: {e}")
            
        return unique_news

    def _get_alt_cache_path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_alt_data.parquet")

    def fetch_alt_data(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch alternative data with persistence.
        Appends current real-time values to a historical cache on disk.
        """
        from src.utils import defaults
        cache_path = self._get_alt_cache_path(ticker)
        today = pd.Timestamp.now().normalize()
        
        # 1. Load existing history
        if os.path.exists(cache_path):
            try:
                history_df = pd.read_parquet(cache_path)
            except Exception as e:
                print(f"Error reading alt data cache: {e}")
                history_df = pd.DataFrame(columns=["Date", "Web_Attention", "Social_Sentiment"])
        else:
            history_df = pd.DataFrame(columns=["Date", "Web_Attention", "Social_Sentiment"])

        # 2. Fetch Current Snapshots (Real Data)
        # Web Attention
        try:
            from src.data.providers import StockTwitsProvider
            st_provider = StockTwitsProvider()
            current_attention = st_provider.fetch_attention(ticker)
        except Exception:
            current_attention = 0.0

        # Sentiment
        try:
            current_sentiment = self.provider.fetch_sentiment(ticker) if Config.ENABLE_REAL_SENTIMENT else 0.0
        except Exception:
            current_sentiment = 0.0
            
        # 3. Update History
        # Check if we already have today's data
        if not history_df.empty and today in history_df['Date'].values:
            # Update today's row
            mask = history_df['Date'] == today
            history_df.loc[mask, "Web_Attention"] = current_attention
            history_df.loc[mask, "Social_Sentiment"] = current_sentiment
        else:
            # Append new row
            new_row = pd.DataFrame([{
                "Date": today,
                "Web_Attention": current_attention,
                "Social_Sentiment": current_sentiment
            }])
            history_df = pd.concat([history_df, new_row], ignore_index=True)
            
        # 4. Save Cache
        try:
            history_df.to_parquet(cache_path)
        except Exception as e:
            print(f"Error saving alt data cache: {e}")

        # 5. Format for Return
        # Ensure we return at least 'days' rows if possible, or backfill if new
        history_df = history_df.set_index("Date").sort_index()
        
        # If very short history (e.g. first run), we project the current value backwards
        # so the chart isn't empty. This is a "Cold Start" strategy.
        if len(history_df) < days:
             # Generate older dates
             needed = days - len(history_df)
             oldest_date = history_df.index[0]
             
             backfill_dates = pd.date_range(end=oldest_date - pd.Timedelta(days=1), periods=needed)
             backfill_df = pd.DataFrame(index=backfill_dates)
             backfill_df["Web_Attention"] = current_attention # Flat line assumption
             backfill_df["Social_Sentiment"] = current_sentiment
             
             history_df = pd.concat([backfill_df, history_df]).sort_index()

        return history_df.tail(days)

    def search_assets(self, query: str) -> list:
        """
        Search for assets matching a query.
        """
        return self.provider.search_assets(query)
        
    def get_fundamentals(self, ticker: str) -> dict:
        """
        Fetch fundamental metrics like P/E.
        """
        try:
            return self.provider.fetch_key_metrics(ticker)
        except Exception as e:
            print(f"Error fetching fundamentals for {ticker}: {e}")
            return {'pe_ratio': 0.0}

if __name__ == "__main__":
    fetcher = DataFetcher()
    # Note: Requires API KEY in .env
    # df = fetcher.fetch_ohlcv("AAPL", period="1mo")
    # print(df.head())
