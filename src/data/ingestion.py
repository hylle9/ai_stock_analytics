import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

class DataFetcher:
    """
    Fetches market data from yfinance with local caching.
    """
    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}.parquet")

    def fetch_ohlcv(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch daily OHLCV data.
        
        Args:
            ticker: Stock ticker symbol
            period: Data period (e.g. "2y", "max")
            use_cache: If True, try to load from local cache first if recent enough
            
        Returns:
            DataFrame with columns [open, high, low, close, volume]
        """
        cache_path = self._get_cache_path(ticker)
        
        # Try cache first
        if use_cache and os.path.exists(cache_path):
            try:
                # Check if cache is fresh (modified today)
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if mtime.date() == datetime.now().date():
                    print(f"Loading {ticker} from cache...")
                    return pd.read_parquet(cache_path)
            except Exception as e:
                print(f"Error reading cache for {ticker}: {e}")

        # Fetch from API
        print(f"Fetching {ticker} from yfinance...")
        try:
            df = yf.download(ticker, period=period, progress=False)
        except Exception as e:
            print(f"Error downloading {ticker}: {e}")
            return pd.DataFrame()
        
        if df.empty:
            print(f"Warning: No data found for {ticker}")
            return pd.DataFrame()
        
        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Standardize
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        # Filter columns
        required_cols = ["open", "high", "low", "close", "volume"]
        available_cols = [c for c in required_cols if c in df.columns]
        df = df[available_cols]
        
        # Save to cache
        if not df.empty:
            try:
                df.to_parquet(cache_path)
            except Exception as e:
                print(f"Error saving cache for {ticker}: {e}")
                
        return df

    def fetch_news(self, ticker: str) -> list:
        """
        Fetch news headlines for a ticker.
        Returns a list of dicts: [{'title': str, 'publisher': str, 'link': str, 'providerPublishTime': int}]
        """
        try:
            t = yf.Ticker(ticker)
            raw_news = t.news
            normalized_news = []
            
            for item in raw_news:
                # Check for new nested structure
                if 'content' in item and item['content'] is not None:
                    content = item['content']
                    try:
                        pub_date = pd.to_datetime(content.get('pubDate'))
                        timestamp = int(pub_date.timestamp())
                    except:
                        timestamp = int(datetime.now().timestamp())

                    normalized_news.append({
                        'title': content.get('title', 'No Title'),
                        'publisher': content.get('provider', {}).get('displayName', 'Unknown') if content.get('provider') else 'Unknown',
                        'link': content.get('clickThroughUrl', {}).get('url', '#') if content.get('clickThroughUrl') else '#',
                        'providerPublishTime': timestamp
                    })
                # Handle potential flat structure (legacy)
                elif 'title' in item:
                    normalized_news.append(item)
            
            return normalized_news
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []

    def fetch_alt_data(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch alternative data.
        1. Web Attention: Google Trends (Real via pytrends, with synthetic fallback)
        2. Social Sentiment: Synthetic (placeholder for Twitter/Reddit API)
        """
        import numpy as np
        from pytrends.request import TrendReq
        
        dates = pd.date_range(end=datetime.now(), periods=days)
        
        # 1. Web Attention (Google Trends)
        attention = None
        try:
            print(f"Fetching Google Trends for {ticker}...")
            pytrends = TrendReq(hl='en-US', tz=360)
            # Build payload (use ticker symbol, maybe add "stock" context if needed)
            kw_list = [ticker] 
            pytrends.build_payload(kw_list, timeframe='today 1-m') # last 1 month
            
            trends_df = pytrends.interest_over_time()
            if not trends_df.empty and ticker in trends_df.columns:
                # Resample/Reindex to match our desired dates if needed, 
                # but usually 'today 1-m' gives daily data.
                # We'll reindex to ensure we have the exact days we want.
                trends_df = trends_df.reindex(dates, method='nearest')
                attention = trends_df[ticker].values
                # Normalize to 0-100 just in case
                attention = np.nan_to_num(attention, nan=0.0)
                print("Successfully fetched Google Trends data.")
        except Exception as e:
            print(f"Google Trends fetch failed ({e}). Using synthetic fallback.")
            
        # Fallback if failed
        if attention is None:
            # Random walk for attention
            att_walk = np.random.normal(0, 1, days).cumsum()
            attention = (att_walk - att_walk.min()) / (att_walk.max() - att_walk.min()) * 100
        
        # 2. Social Sentiment (Synthetic)
        # Random sentiment (-1 to 1)
        sentiment = np.random.uniform(-0.8, 0.8, days)
        
        return pd.DataFrame({
            "Date": dates,
            "Web_Attention": attention,
            "Social_Sentiment": sentiment
        }).set_index("Date")

if __name__ == "__main__":
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("AAPL", period="1mo")
    print(df.head())
