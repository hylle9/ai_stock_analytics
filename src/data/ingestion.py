import pandas as pd
import os
import numpy as np
import json
from datetime import datetime, timedelta
from src.utils.config import Config
from src.data.providers import AlphaVantageProvider, BaseDataProvider, YFinanceProvider
from src.data.db_provider import DuckDBProvider
from src.utils.profiling import Timer

class DataFetcher:
    """
    Central Data Access Object (DAO) for the application.
    
    This class abstracts away WHERE the data comes from (API, Database, or File Cache).
    It implements the "Smart Caching" pattern:
    1. Try to load data from the local database (Fast, Free).
    2. If missing or stale, fetch from Live API (Slow, Costs Money/Quota).
    3. Save the live data back to the database for next time.
    4. Fallback to other providers if one fails (e.g. AlphaVantage -> Yahoo Finance).
    """
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize the Fetcher.
        Sets up connections to the Database and API Providers based on Config.
        """
        # Define where file-based caches (backups) are stored
        self.cache_dir = cache_dir or Config.DATA_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.db = None
        self.live_provider = None
        self.date_cache = {} # In-memory cache to avoid hitting DB for metadata repeatedly
        
        # 1. Setup DB Provider (DuckDB)
        # This is our primary storage for historical data.
        if Config.USE_SYNTHETIC_DB:
             self.db = DuckDBProvider()
             
        # 2. Setup Live Provider (API)
        # We check if a valid API Key exists for Alpha Vantage.
        av_key = Config.ALPHA_VANTAGE_API_KEY
        if av_key and "your_" not in av_key.lower() and len(av_key) > 5:
             self.live_provider = AlphaVantageProvider()
        else:
             # Fallback to Yahoo Finance (Free, no key required) if no AV key
             self.live_provider = YFinanceProvider()
             
        # Select the 'default' provider based on strategy (mostly for legacy calls)
        if Config.DATA_STRATEGY == "SYNTHETIC":
             self.provider = self.db
        elif Config.DATA_STRATEGY == "LIVE":
             self.provider = self.live_provider
        else:
             self.provider = self.live_provider

    def _get_cache_path(self, ticker: str, period: str) -> str:
        """Helper to get file path for legacy Parquet cache."""
        return os.path.join(self.cache_dir, f"{ticker}_{period}.parquet")
        
    def warmup_cache(self):
        """
        Performance Optimization:
        Pre-loads the 'latest available date' for all tickers from the DB into memory.
        This allows us to instantly know if we need to fetch new data without querying the DB every time.
        """
        if self.db:
            with Timer("DB:WarmupDates"):
                self.date_cache = self.db.get_latest_dates_map()
                print(f"🔥 Cache Warmed: {len(self.date_cache)} tickers loaded.")

    def fetch_ohlcv(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Main function to get Stock Price Data (Open, High, Low, Close, Volume).
        
        Args:
            ticker: The stock symbol (e.g., 'AAPL')
            period: How much history to get (e.g., '2y', 'max')
            use_cache: If True, try to load from DB first.
            
        Returns:
            pd.DataFrame: DataFrame with DateTime index and price columns.
        """
        
        # --- STRATEGY: LIVE (Production Mode) ---
        # Logic: Check DB -> If Stale, Fetch Live -> Save to DB -> Return
        if Config.DATA_STRATEGY in ["LIVE", "PRODUCTION"]:
             
             # 0. Smart Cache Check (Optimization)
             if self.db and use_cache:
                 try:
                     with Timer(f"SmartCheck::{ticker}"):
                         # Check in-memory map first
                         latest_date_str = self.date_cache.get(ticker)
                         if not latest_date_str:
                              # If not in memory, ask DB (maybe it's a new ticker)
                              latest_date_str = self.db.get_latest_date(ticker)
                              
                         if latest_date_str:
                             latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
                             today = datetime.now().date()
                             
                             # Definition of "Fresh":
                             # 1. Latest date is today or yesterday (normal trading)
                             # 2. If Today is Weekend, Latest date is Friday
                             is_fresh = False
                             if latest_date >= today - timedelta(days=1):
                                 is_fresh = True
    
                             if is_fresh:
                                 print(f"✨ Smart Cache: Found fresh data for {ticker} in DB.")
                                 with Timer(f"DBFetch::{ticker}"):
                                     # It's fresh, so just return DB data! Fast!
                                     df = self.db.fetch_ohlcv(ticker, period)
                                 
                                 if not df.empty:
                                     is_prod = Config.DATA_STRATEGY == "PRODUCTION"
                                     # Tag source primarily for UI debugging
                                     source_tag = "live" if is_prod else "🟠 CACHE (DB)"
                                     df.attrs["source"] = source_tag
                                     if 'source' not in df.columns: df['source'] = source_tag
                                     return df
                 except Exception as e:
                     print(f"Smart Cache Error: {e}")

             # 1. Fetch Live (If cache missed or stale)
             # Skip this for special internal tickers like "$MARKET"
             if ticker == "$MARKET":
                 if self.db:
                      df = self.db.fetch_ohlcv(ticker, period)
                      if not df.empty:
                          df.attrs["source"] = "🟠 CACHE (DB)" 
                          return df
                 return pd.DataFrame()

             print(f"📡 Fetching live data for {ticker}...")
             try:
                 df = self.live_provider.fetch_ohlcv(ticker, period)
                 
                 # Provider Fallback (AV -> YF)
                 if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                      print("Switching to YFinance (Fallback)...")
                      df = YFinanceProvider().fetch_ohlcv(ticker, period)
                 
                 if not df.empty:
                     # 2. Save to DB for next time
                     if self.db: 
                         print(f"💾 Saving to DB...")
                         self.db.save_ohlcv(ticker, df, source="live")
                     
                     df.attrs["source"] = "🟢 LIVE"
                     df['source'] = 'live'
                     return df
             except Exception as e:
                 print(f"Live Fetch Error: {e}")
            
             # 3. Last Resort: DB History
             # If Live API fails (e.g. no internet), show what historical data we HAVE in DB.
             if self.db:
                 print(f"⚠️ Live failed. Falling back to DB for {ticker}")
                 df = self.db.fetch_ohlcv(ticker, period)
                 if not df.empty:
                     df.attrs["source"] = "🟠 CACHE (DB)"
                     if 'source' not in df.columns: df['source'] = "🟠 CACHE (DB)"
                     return df
             
             return pd.DataFrame() # Give up

        # --- STRATEGY: SYNTHETIC (Offline Dev Mode) ---
        # Logic: DB First (Even if stale) -> Live -> Save
        if Config.DATA_STRATEGY == "SYNTHETIC":
            # 1. Try DB unconditionally
            if self.db:
                df = self.db.fetch_ohlcv(ticker, period)
                if not df.empty:
                    df.attrs["source"] = "🟠 CACHE (DB)"
                    return df
            
            # 2. Fallback Live (Only if DB barely has anything)
            print(f"📉 DB Miss for {ticker}. Fetching from Live API...")
            try:
                df = self.live_provider.fetch_ohlcv(ticker, period)
                # Fallback logic same as above
                if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                     df = YFinanceProvider().fetch_ohlcv(ticker, period)
                
                if not df.empty and self.db:
                    self.db.save_ohlcv(ticker, df, source="live")
                    df.attrs["source"] = "🟢 LIVE"
                    return df
            except Exception as e:
                print(f"Fallback Error for {ticker}: {e}")
            
            return pd.DataFrame()

        # --- LEGACY FILE CACHE CODE REMOVED FOR CLARITY ---
        # (The above 2 strategies cover all modern cases)
        return pd.DataFrame()

    def fetch_batch_ohlcv(self, tickers: list[str], period: str = "2y") -> dict:
        """
        Optimized Batch Fetching.
        Instead of running `fetch_ohlcv` 100 times (100 DB queries),
        we run ONE big DB query to get all 100 tickers at once.
        """
        results = {}
        if self.db:
             with Timer(f"BatchDBFetch::{len(tickers)}"):
                 results = self.db.fetch_batch_ohlcv(tickers, period)
                 print(f"Batch DB returned {len(results)}/{len(tickers)} tickers.")
                 for t, df in results.items():
                     df.attrs["source"] = "🟠 CACHE (DB Batch)"
        else:
             print("❌ No DB configured for Batch Fetch!")
        
        # Identify missing tickers (Cache Misses)
        missing = [t for t in tickers if t not in results]
        
        # Fetch missing tickers one-by-one (Fallback)
        # We don't have a specific "Batch API" for AV/YF implemented yet,
        # so we loop.
        if missing:
             print(f"⚠️ Batch Fetch Miss: {len(missing)} tickers missing (falling back to sequential)")
             with Timer(f"BatchFallback::{len(missing)}"):
                 for t in missing:
                     results[t] = self.fetch_ohlcv(t, period)
                 
        return results

    
    def _get_news_cache_path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_news.json")

    def fetch_news(self, ticker: str, limit: int = 10) -> list:
        """
        Fetch news articles.
        Prioritizes Live API for news as it goes stale very quickly.
        """
        # --- STRATEGY: LIVE (API First) ---
        if Config.DATA_STRATEGY == "LIVE":
            try:
                # 1. Live
                print(f"📰 Fetching Live News for {ticker}...")
                news = self.live_provider.fetch_news(ticker, limit)
                
                # Provider Fallback
                if not news and isinstance(self.live_provider, AlphaVantageProvider):
                    news = YFinanceProvider().fetch_news(ticker, limit)
                
                if news:
                    # Save to DB for context/history
                    if self.db: self.db.save_news(ticker, news)
                    for n in news: n["_source"] = "🟢 LIVE"
                    return news
            except Exception as e:
                print(f"Live News Error: {e}")
            
            # 2. Fallback DB (Show old news is better than no news)
            if self.db:
                print("Falling back to DB news...")
                news = self.db.fetch_news(ticker, limit)
                for n in news: n["_source"] = "🟠 CACHE (DB)"
                return news
            return []

        # --- STRATEGY: SYNTHETIC (DB First) ---
        if Config.DATA_STRATEGY == "SYNTHETIC":
            # 1. DB
            if self.db:
                news = self.db.fetch_news(ticker, limit)
                if news: return news
            
            # 2. Live
            try:
                news = self.live_provider.fetch_news(ticker, limit)
                if not news and isinstance(self.live_provider, AlphaVantageProvider):
                    news = YFinanceProvider().fetch_news(ticker, limit)
                
                if news and self.db:
                    self.db.save_news(ticker, news)
                    for n in news: n["_source"] = "🟢 LIVE"
                    return news
            except Exception as e:
                print(f"News Fallback Error: {e}")
            return []

        # Legacy File Cache Logic Omitted for brevity (handled by strategies above)
        return []

    def fetch_alt_data(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        Fetches Alternative Data (Web Attention, Social Sentiment).
        This data comes from providers like StockTwits or is simulated.
        """
        today = pd.Timestamp.now().normalize()
        history_df = pd.DataFrame(columns=["Date", "Web_Attention", "Social_Sentiment"])

        # 1. Load existing history from DB
        if Config.USE_SYNTHETIC_DB and self.db:
             try:
                 df = self.db.fetch_alt_history(ticker, days=days) 
                 if not df.empty:
                     history_df = df.reset_index().rename(columns={"date": "Date"})
                     # Ensure columns exist
                     if "Web_Attention" not in history_df: history_df["Web_Attention"] = 0.0
                     if "Social_Sentiment" not in history_df: history_df["Social_Sentiment"] = 0.0
             except Exception as e:
                 print(f"DB Load Alt Error: {e}")

        # 2. Determine if we need to fetch live data for Today
        need_fetch = False
        has_today = False
        
        # Check if we already have today's row in history
        if not history_df.empty:
             history_df["Date"] = pd.to_datetime(history_df["Date"]).dt.normalize()
             if today in history_df['Date'].values:
                 has_today = True

        # Logic for fetching
        if Config.DATA_STRATEGY in ["LIVE", "PRODUCTION"]:
            # In Production, trust DB if present, else fetch
            if Config.DATA_STRATEGY == "PRODUCTION" and has_today:
                need_fetch = False
            else:
                need_fetch = True # Force refresh in dev/live
        elif Config.DATA_STRATEGY == "SYNTHETIC":
            need_fetch = not has_today

        # 3. Fetch Data if needed
        current_attention = 0.0
        current_sentiment = 0.0

        if need_fetch:
            print(f"🌍 Fetching Live Alt Data for {ticker}...")
            
            # A. Web Attention (StockTwits)
            try:
                from src.data.providers import StockTwitsProvider
                st_provider = StockTwitsProvider()
                current_attention = st_provider.fetch_attention(ticker)
            except Exception: pass

            # B. Sentiment (AlphaVantage / YFinance)
            try:
                if self.live_provider:
                    current_sentiment = self.live_provider.fetch_sentiment(ticker)
            except Exception: pass
            
            # C. Update History DataFrame
            new_row = {"Date": today, "Web_Attention": float(current_attention), "Social_Sentiment": float(current_sentiment)}
            
            if has_today:
                # Overwrite today's row with fresh data
                mask = history_df['Date'] == today
                history_df.loc[mask, "Web_Attention"] = float(current_attention)
                history_df.loc[mask, "Social_Sentiment"] = float(current_sentiment)
            else:
                # Append new row
                history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
            
            # D. Save to DB
            if Config.USE_SYNTHETIC_DB and self.db:
                self.db.save_alt_data(ticker, today.date(), current_sentiment, current_attention, source="live")

        # 4. Final Formatting
        history_df = history_df.set_index("Date").sort_index()
        
        # Cold Start Fix: If we have < 30 days of data, 
        # we flat-line backfill the current value so the chart looks decent.
        if len(history_df) < days:
             needed = days - len(history_df)
             oldest_date = history_df.index[0] if not history_df.empty else today
             
             backfill_dates = pd.date_range(end=oldest_date - pd.Timedelta(days=1), periods=needed)
             backfill_df = pd.DataFrame(index=backfill_dates)
             backfill_df["Web_Attention"] = current_attention 
             backfill_df["Social_Sentiment"] = current_sentiment
             
             history_df = pd.concat([backfill_df, history_df]).sort_index()

        return history_df.tail(days)

    def get_company_profile(self, ticker: str) -> dict:
        """
        Fetches static company data (Sector, Industry, Description).
        """
        profile = {}
        
        # 0. Try DB First (Optimization, this data rarely changes)
        if Config.USE_SYNTHETIC_DB and self.db:
            try:
                db_profile = self.db.fetch_key_metrics(ticker)
                if db_profile and db_profile.get('name'):
                    db_profile["_source"] = "🟠 CACHE (DB)"
                    return db_profile
            except Exception: pass

        # 1. Try Live (If missing in DB)
        if self.live_provider:
            try:
                print(f"🏢 Fetching Profile for {ticker}...")
                profile = self.live_provider.fetch_key_metrics(ticker)
                
                # Save to DB
                if profile and self.db:
                   self.db.add_asset(
                       ticker, 
                       name=profile.get("name", ""), 
                       sector=profile.get("sector", ""), 
                       industry=profile.get("industry", ""),
                       description=profile.get("description", "")
                   )
                if profile: profile["_source"] = "🟢 LIVE"
            except Exception as e:
                print(f"Profile Fetch Error: {e}")
        
        return profile
        
    def search_assets(self, query: str) -> list:
        """Proxies the search request to the provider."""
        return self.provider.search_assets(query)
        
    def get_fundamentals(self, ticker: str, allow_fallback: bool = True) -> dict:
        """
        Fetches fundamentals like P/E Ratio, Market Cap.
        Has robust fallback chain: DB -> AlphaVantage -> YahooFinance.
        """
        if ticker.startswith("$"): return {'pe_ratio': 0.0, 'market_cap': 0.0}

        # 1. DB
        if Config.USE_SYNTHETIC_DB and self.db:
             data = self.db.fetch_key_metrics(ticker)
             data["_source"] = "🟠 CACHE (DB)"
             
             if not allow_fallback: return data

             # If data looks valid, return it
             if data.get('market_cap', 0) > 0 or data.get('pe_ratio', 0) > 0:
                 return data
             
             # Metric Fallback Chain
             try:
                data = {}
                # Try Alpha Vantage
                if Config.ALPHA_VANTAGE_API_KEY:
                    try: data = AlphaVantageProvider().fetch_key_metrics(ticker)
                    except: pass
                
                # Try YFinance
                if not data.get('pe_ratio') and not data.get('market_cap'):
                    try: data = YFinanceProvider().fetch_key_metrics(ticker)
                    except: pass
                
                if data:
                    if self.db: self.db.save_fundamentals(ticker, data)
                    data["_source"] = "🟢 LIVE"
                    return data
                    
             except Exception as e:
                print(f"Fund Fallback Error: {e}")
                return {'pe_ratio': 0.0}

        # Legacy Provider approach
        try:
            return self.provider.fetch_key_metrics(ticker)
        except Exception:
            return {'pe_ratio': 0.0}

if __name__ == "__main__":
    fetcher = DataFetcher()
    # Test
    # df = fetcher.fetch_ohlcv("AAPL", period="1mo")
    # print(df.head())
