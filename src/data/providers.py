from abc import ABC, abstractmethod
import pandas as pd
import requests
from datetime import datetime
from src.utils.config import Config

class BaseDataProvider(ABC):
    """
    Abstract base class for market data providers.
    """
    
    @abstractmethod
    def fetch_ohlcv(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        """
        Fetch OHLCV data.
        Returns: DataFrame with columns [open, high, low, close, volume]
        """
        pass

    @abstractmethod
    def fetch_news(self, ticker: str) -> list:
        """
        Fetch news items.
        Returns: List of dicts [{'title', 'publisher', 'link', 'providerPublishTime'}]
        """
        pass

    @abstractmethod
    def fetch_sentiment(self, ticker: str) -> float:
        """
        Fetch sentiment score (-1 to 1).
        """
        pass

    @abstractmethod
    def search_assets(self, query: str) -> list:
        """
        Search for assets by name or ticker.
        Returns: List of dicts [{'symbol', 'name', 'type', 'region', 'matchScore'}]
        """
        pass

class StockTwitsProvider:
    """
    StockTwits API for social attention/volume.
    """
    BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{}.json"
    
    def fetch_attention(self, ticker: str) -> float:
        """
        Returns number of messages in last 30 messages (proxy for velocity).
        Normalized against a baseline (e.g. 30 messages = 100 max for this demo).
        """
        try:
            url = self.BASE_URL.format(ticker)
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                messages = data.get('messages', [])
                # Proxy: Just count messages in the current batch (default 30)
                # In a real app we'd count msg/hour.
                count = len(messages)
                return min(100.0, (count / 30.0) * 100.0)
        except Exception as e:
            print(f"StockTwits Error: {e}")
        return 0.0

class AlphaVantageProvider(BaseDataProvider):
    """
    Alpha Vantage API implementation.
    """
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self):
        self.api_key = Config.ALPHA_VANTAGE_API_KEY
        if not self.api_key:
            print("Warning: No Alpha Vantage API key found.")
            
    def _make_request(self, function: str, symbol: str = None, **kwargs):
        params = {
            "function": function,
            "apikey": self.api_key,
            **kwargs
        }
        if symbol:
            params["symbol"] = symbol
            
        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Alpha Vantage Request Error: {e}")
            return {}

    def fetch_ohlcv(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        # Note: Alpha Vantage free tier has limits. 
        # Ideally we'd map 'period' to outputsize (compact/full).
        data = self._make_request("TIME_SERIES_DAILY", ticker, outputsize="full")
        
        ts_data = data.get("Time Series (Daily)", {})
        if not ts_data:
            return pd.DataFrame()
            
        df = pd.DataFrame.from_dict(ts_data, orient='index')
        df = df.rename(columns={
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. volume": "volume"
        })
        df.index = pd.to_datetime(df.index)
        df = df.astype(float)
        df = df.sort_index()
        
        # Filter by period (naive implementation)
        # Real impl would parse period string.
        # Defaulting to returning all fetched data for now.
        return df

    def fetch_news(self, ticker: str) -> list:
        data = self._make_request("NEWS_SENTIMENT", ticker, limit=50)
        feed = data.get("feed", [])
        
        normalized = []
        for item in feed:
            try:
                # AV returns time like '20230101T123000'
                pub_time_str = item.get('time_published', '')
                dt = datetime.strptime(pub_time_str, "%Y%m%dT%H%M%S")
                timestamp = int(dt.timestamp())
                
                normalized.append({
                    'title': item.get('title'),
                    'publisher': item.get('source'),
                    'link': item.get('url'),
                    'providerPublishTime': timestamp,
                    'sentiment_score': float(item.get('overall_sentiment_score', 0))
                })
            except Exception:
                continue
                
        return normalized

    def fetch_sentiment(self, ticker: str) -> float:
        # Re-uses the news endpoint but aggregates specific ticker sentiment
        data = self._make_request("NEWS_SENTIMENT", ticker, limit=50)
        # AV provides 'ticker_sentiment' list in each news item
        
        total_score = 0
        count = 0
        
        for item in data.get("feed", []):
            for tick in item.get("ticker_sentiment", []):
                if tick['ticker'] == ticker:
                    total_score += float(tick['ticker_sentiment_score'])
                    count += 1
                    
        return total_score / count if count > 0 else 0.0

    def fetch_attention(self, ticker: str) -> float:
        return 0.0
        
    def search_assets(self, query: str) -> list:
        data = self._make_request("SYMBOL_SEARCH", keywords=query)
        matches = data.get("bestMatches", [])
        
        results = []
        for match in matches:
            results.append({
                'symbol': match.get('1. symbol'),
                'name': match.get('2. name'),
                'type': match.get('3. type'),
                'region': match.get('4. region'),
                'matchScore': float(match.get('9. matchScore', 0.0))
            })
        return results

class YFinanceProvider(BaseDataProvider):
    """
    Legacy YFinance provider (Wrapper).
    """
    def fetch_ohlcv(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        import yfinance as yf
        try:
            df = yf.download(ticker, period=period, progress=False)
            if df.empty:
                return pd.DataFrame()
            
            # Helper to clean multi-index if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
            })
            
            # Ensure columns exist and are lowercase
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            print(f"YFinance OHLCV unexpected error: {e}")
            return pd.DataFrame()

    def fetch_news(self, ticker: str) -> list:
        import yfinance as yf
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
                        'providerPublishTime': timestamp,
                        'sentiment_score': 0.0 # YF doesn't provide sentiment score directly
                    })
                # Handle potential flat structure (legacy)
                elif 'title' in item:
                    normalized_news.append(item)
            
            return normalized_news
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []

    def fetch_sentiment(self, ticker: str) -> float:
        return 0.0 # Not supported
        
    def fetch_attention(self, ticker: str) -> float:
        return 0.0
        
    def search_assets(self, query: str) -> list:
        # Check if we should use this fallback (if user has no AV key this will be active)
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 10, "newsCount": 0}
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        try:
            resp = requests.get(url, params=params, headers=headers)
            data = resp.json()
            quotes = data.get("quotes", [])
            
            results = []
            for q in quotes:
                # Filter useful types
                if q.get('quoteType') in ['EQUITY', 'ETF', 'MUTUALFUND']:
                    results.append({
                        'symbol': q.get('symbol'),
                        'name': q.get('shortname') or q.get('longname'),
                        'type': q.get('quoteType'),
                        'region': q.get('exchange'),
                        'matchScore': float(q.get('score', 0.0))
                    })
            return results
        except Exception as e:
            print(f"YFinance search error: {e}")
            return []
