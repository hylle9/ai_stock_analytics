import pandas as pd
import os
import numpy as np
from datetime import datetime, timedelta
from src.utils.config import Config
from src.data.providers import AlphaVantageProvider, BaseDataProvider, YFinanceProvider
from src.data.providers import AlphaVantageProvider, BaseDataProvider, YFinanceProvider
from src.data.db_provider import DuckDBProvider
from src.utils.profiling import Timer

class DataFetcher:
    """
    Fetches market data using configured providers.
    Wrapper around BaseDataProvider with caching layer.
    """
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or Config.DATA_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.db = None
        self.live_provider = None
        self.date_cache = {}
        
        # 1. Setup DB Provider (if enabled)
        if Config.USE_SYNTHETIC_DB:
             self.db = DuckDBProvider()
             
        # 2. Setup Live Provider (Always available for fallback or primary)
        av_key = Config.ALPHA_VANTAGE_API_KEY
        if av_key and "your_" not in av_key.lower() and len(av_key) > 5:
             self.live_provider = AlphaVantageProvider()
        else:
             self.live_provider = YFinanceProvider()
             
        # Backwards compatibility / Default accessor
        if Config.DATA_STRATEGY == "SYNTHETIC":
             self.provider = self.db
        elif Config.DATA_STRATEGY == "LIVE":
             self.provider = self.live_provider
        else:
             self.provider = self.live_provider

    def _get_cache_path(self, ticker: str, period: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_{period}.parquet")
        
    def warmup_cache(self):
        """Pre-fetch metadata to speed up subsequent calls."""
        if self.db:
            with Timer("DB:WarmupDates"):
                self.date_cache = self.db.get_latest_dates_map()
                print(f"🔥 Cache Warmed: {len(self.date_cache)} tickers loaded.")

    def fetch_ohlcv(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch daily OHLCV data.
        """
    def fetch_ohlcv(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch daily OHLCV data based on Config.DATA_STRATEGY.
        """
        # --- STRATEGY: LIVE (API First -> Save DB -> Fallback DB) ---
        if Config.DATA_STRATEGY in ["LIVE", "PRODUCTION"]:
             # 0. Smart Cache Optimization
             # Even in Live Mode, if we have "Fresh" data in DB, use it.
             if self.db:
                 try:
                     with Timer(f"SmartCheck::{ticker}"):
                         # Check in-memory cache first, then fall back to DB query
                         latest_date_str = self.date_cache.get(ticker)
                         if not latest_date_str:
                              latest_date_str = self.db.get_latest_date(ticker)
                              
                         if latest_date_str:
                             latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
                             today = datetime.now().date()
                             
                             # Simple Freshness: Is latest date >= today (or is it weekend?)
                             is_fresh = False
                             if latest_date >= today - timedelta(days=1):
                                 is_fresh = True
    
                             if is_fresh:
                                 print(f"✨ Smart Cache: Found fresh data for {ticker} in DB.")
                                 with Timer(f"DBFetch::{ticker}"):
                                     df = self.db.fetch_ohlcv(ticker, period)
                                 
                                 if not df.empty:
                                     # In PRODUCTION, we trust the DB as "Real History"
                                     is_prod = Config.DATA_STRATEGY == "PRODUCTION"
                                     source_tag = "live" if is_prod else "🟠 CACHE (DB)"
                                     df.attrs["source"] = source_tag
                                     if 'source' not in df.columns: df['source'] = source_tag
                                     return df
                 except Exception as e:
                     print(f"Smart Cache Error: {e}")

     # 1. Try Live
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
                 if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                      print("Switching to YFinance...")
                      df = YFinanceProvider().fetch_ohlcv(ticker, period)
                 
                 if not df.empty:
                     if self.db: 
                         print(f"💾 Saving to DB...")
                         self.db.save_ohlcv(ticker, df, source="live")
                     df.attrs["source"] = "🟢 LIVE"
                     df['source'] = 'live'
                     return df
             except Exception as e:
                 print(f"Live Fetch Error: {e}")
            
             # 2. Fallback DB
             if self.db:
                 print(f"⚠️ Live failed. Falling back to DB for {ticker}")
                 df = self.db.fetch_ohlcv(ticker, period)
                 if not df.empty:
                     # In PRODUCTION, we trust the DB as "Real History"
                     is_prod = Config.DATA_STRATEGY == "PRODUCTION"
                     source_tag = "live" if is_prod else "🟠 CACHE (DB)"
                     df.attrs["source"] = source_tag
                     if 'source' not in df.columns: df['source'] = source_tag
                     return df
             return pd.DataFrame()

        # --- STRATEGY: SYNTHETIC (DB First -> Live -> Save DB) ---
        if Config.DATA_STRATEGY == "SYNTHETIC":
            # 1. Try DB
            if self.db:
                df = self.db.fetch_ohlcv(ticker, period)
                if not df.empty:
                    df.attrs["source"] = "🟠 CACHE (DB)"
                    return df
            
            # 2. Fallback Live
            print(f"📉 DB Miss for {ticker}. Fetching from Live API...")
            try:
                df = self.live_provider.fetch_ohlcv(ticker, period)
                if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                     df = YFinanceProvider().fetch_ohlcv(ticker, period)
                
                if not df.empty and self.db:
                    self.db.save_ohlcv(ticker, df, source="live")
                    df.attrs["source"] = "🟢 LIVE"
                    return df
            except Exception as e:
                print(f"Fallback Error for {ticker}: {e}")
            
            return pd.DataFrame()

        # --- STRATEGY: LEGACY (File Cache) ---
        # Falls through to existing lines 70+
        cache_path = self._get_cache_path(ticker, period)
        
        # Try cache first
        if use_cache and os.path.exists(cache_path):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if mtime.date() == datetime.now().date():
                    print(f"Loading {ticker} from cache...")
                    df = pd.read_parquet(cache_path)
                    df.attrs["source"] = "🟡 CACHE (File)"
                    return df
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
        
        # If we got here, it was a fresh fetch (Live) not in cache
        df.attrs["source"] = "🟢 LIVE"
        return df

    def fetch_batch_ohlcv(self, tickers: list[str], period: str = "2y") -> dict:
        """
        Batch fetch optimized for DB.
        """
        results = {}
        if self.db:
             with Timer(f"BatchDBFetch::{len(tickers)}"):
                 results = self.db.fetch_batch_ohlcv(tickers, period)
                 print(f"Batch DB returned {len(results)}/{len(tickers)} tickers.")
                 # Tag them
                 for t, df in results.items():
                     df.attrs["source"] = "🟠 CACHE (DB Batch)"
        else:
             print("❌ No DB configured for Batch Fetch!")
        
        # Fill missing with sequential (cache misses or if no DB)
        missing = [t for t in tickers if t not in results]
        if missing:
             print(f"⚠️ Batch Fetch Miss: {len(missing)} tickers missing (falling back to sequential): {missing}")
             with Timer(f"BatchFallback::{len(missing)}"):
                 for t in missing:
                     results[t] = self.fetch_ohlcv(t, period)
                 
        return results

    def fetch_ohlcv_legacy(self, ticker: str, period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch daily OHLCV data.
        """
        # --- STRATEGY: LIVE (API First -> Save DB -> Fallback DB) ---
        if Config.DATA_STRATEGY == "LIVE":
             # 0. Smart Cache Optimization
             # Even in Live Mode, if we have "Fresh" data in DB, use it.
             if self.db:
                 with Timer(f"SmartCheck::{ticker}"):
                     # Check in-memory cache first, then fall back to DB query
                     latest_date_str = self.date_cache.get(ticker)
                     if not latest_date_str:
                          latest_date_str = self.db.get_latest_date(ticker)
                          
                     if latest_date_str:
                         latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
                         today = datetime.now().date()
                         
                         # Simple Freshness: Is latest date >= today (or is it weekend?)
                         # If today is Sat/Sun, and latest is Friday, it's fresh.
                         is_fresh = False
                         if latest_date >= today:
                             is_fresh = True
                         elif today.weekday() >= 5: # Sat=5, Sun=6
                             # If weekend, check if we have Friday
                             # (Logic simplified: if latest is within 2 days)
                             delta = (today - latest_date).days
                             if delta <= 2:
                                 is_fresh = True
                         elif latest_date == today: # Explicit catch
                             is_fresh = True

                         if is_fresh:
                             print(f"✨ Smart Cache: Found fresh data for {ticker} in DB.")
                             with Timer(f"DBFetch::{ticker}"):
                                 df = self.db.fetch_ohlcv(ticker, period)
                             if not df.empty:
                                 df.attrs["source"] = "🟠 CACHE (DB)"
                                 return df

             # 1. Try Live
             print(f"📡 Fetching live data for {ticker}...")
             try:
                 df = self.live_provider.fetch_ohlcv(ticker, period)
                 if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                      print("Switching to YFinance...")
                      df = YFinanceProvider().fetch_ohlcv(ticker, period)
                 
                 if not df.empty:
                     if self.db: 
                         print(f"💾 Saving to DB...")
                         self.db.save_ohlcv(ticker, df, source="live")
                     df.attrs["source"] = "🟢 LIVE"
                     return df
             except Exception as e:
                 print(f"Live Fetch Error: {e}")
            
             # 2. Fallback DB
             if self.db:
                 print(f"⚠️ Live failed. Falling back to DB for {ticker}")
                 df = self.db.fetch_ohlcv(ticker, period)
                 if not df.empty:
                     df.attrs["source"] = "🟠 CACHE (DB)"
                     return df
             return pd.DataFrame()

        # --- STRATEGY: SYNTHETIC (DB First -> Live -> Save DB) ---
        if Config.DATA_STRATEGY == "SYNTHETIC":
            # 1. Try DB
            if self.db:
                df = self.db.fetch_ohlcv(ticker, period)
                if not df.empty:
                    df.attrs["source"] = "🟠 CACHE (DB)"
                    return df
            
            # 2. Fallback Live
            print(f"📉 DB Miss for {ticker}. Fetching from Live API...")
            try:
                df = self.live_provider.fetch_ohlcv(ticker, period)
                if df.empty and isinstance(self.live_provider, AlphaVantageProvider):
                     df = YFinanceProvider().fetch_ohlcv(ticker, period)
                
                if not df.empty and self.db:
                    self.db.save_ohlcv(ticker, df, source="live")
                    df.attrs["source"] = "🟢 LIVE"
                    return df
            except Exception as e:
                print(f"Fallback Error for {ticker}: {e}")
            
            return pd.DataFrame()

        # --- STRATEGY: LEGACY (File Cache) ---
        # Falls through to existing lines 70+
        cache_path = self._get_cache_path(ticker, period)
        
        # Try cache first
        if use_cache and os.path.exists(cache_path):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if mtime.date() == datetime.now().date():
                    print(f"Loading {ticker} from cache...")
                    df = pd.read_parquet(cache_path)
                    df.attrs["source"] = "🟡 CACHE (File)"
                    return df
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
        
        # If we got here, it was a fresh fetch (Live) not in cache
        df.attrs["source"] = "🟢 LIVE"
        return df

    
    def _get_news_cache_path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker}_news.json")

    def fetch_news(self, ticker: str, limit: int = 10) -> list:
        """
        Fetch news with persistence (DB or JSON).
        """
        # --- STRATEGY: LIVE (API First) ---
        if Config.DATA_STRATEGY == "LIVE":
            try:
                # 1. Live
                print(f"📰 Fetching Live News for {ticker}...")
                news = self.live_provider.fetch_news(ticker, limit)
                if not news and isinstance(self.live_provider, AlphaVantageProvider):
                    news = YFinanceProvider().fetch_news(ticker, limit)
                
                if news:
                    if self.db: self.db.save_news(ticker, news)
                    for n in news: n["_source"] = "🟢 LIVE"
                    return news
            except Exception as e:
                print(f"Live News Error: {e}")
            
            # 2. Fallback DB
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

        # --- STRATEGY: LEGACY (File Cache) ---
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
        """
        today = pd.Timestamp.now().normalize()
        history_df = pd.DataFrame(columns=["Date", "Web_Attention", "Social_Sentiment"])

        # 1. Load existing history (Always try DB first for history context)
        if Config.USE_SYNTHETIC_DB and self.db:
             try:
                 df = self.db.fetch_alt_history(ticker, days=days) 
                 if not df.empty:
                     history_df = df.reset_index().rename(columns={"date": "Date"})
                     if "Web_Attention" not in history_df: history_df["Web_Attention"] = 0.0
                     if "Social_Sentiment" not in history_df: history_df["Social_Sentiment"] = 0.0
             except Exception as e:
                 print(f"DB Load Alt Error: {e}")
        else:
            # Legacy File Cache
            from src.utils import defaults
            cache_path = self._get_alt_cache_path(ticker)
            if os.path.exists(cache_path):
                try:
                    history_df = pd.read_parquet(cache_path)
                except Exception as e:
                    print(f"Error reading alt data cache: {e}")

        # 2. Determine if we need to fetch live data for Today
        need_fetch = False
        
        # Check cache freshness
        has_today = False
        if not history_df.empty:
             history_df["Date"] = pd.to_datetime(history_df["Date"]).dt.normalize()
             if today in history_df['Date'].values:
                 has_today = True

        if Config.DATA_STRATEGY in ["LIVE", "PRODUCTION"]:
            # In PRODUCTION, trust the DB cache for today if it exists
            if Config.DATA_STRATEGY == "PRODUCTION" and has_today:
                print(f"✨ Smart Cache: Found fresh data for {ticker} in DB.")
                need_fetch = False
            else:
                # Live mode typically wants real-time updates, or strictly forcing refresh
                need_fetch = True
        elif Config.DATA_STRATEGY == "SYNTHETIC":
            # Only fetch if missing
            need_fetch = not has_today
        else:
            # Legacy default
            need_fetch = not has_today

        # Initialize for backfill scope
        current_attention = 0.0
        current_sentiment = 0.0

        if need_fetch:
            print(f"🌍 Fetching Live Alt Data for {ticker}...")
            # Web Attention
            current_attention = 0.0
            try:
                from src.data.providers import StockTwitsProvider
                st_provider = StockTwitsProvider()
                current_attention = st_provider.fetch_attention(ticker)
            except Exception:
                pass

            # Sentiment (Use live provider)
            current_sentiment = 0.0
            try:
                if self.live_provider:
                    current_sentiment = self.live_provider.fetch_sentiment(ticker)
            except Exception:
                pass
            
            # 3. Update History
            # If we have today's row, update it, else append
            new_row = {"Date": today, "Web_Attention": float(current_attention), "Social_Sentiment": float(current_sentiment)}
            
            if has_today:
                # Update existing
                mask = history_df['Date'] == today
                history_df.loc[mask, "Web_Attention"] = float(current_attention)
                history_df.loc[mask, "Social_Sentiment"] = float(current_sentiment)
            else:
                # Append
                history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
            
            # 4. Save Cache
            if Config.USE_SYNTHETIC_DB and self.db:
                self.db.save_alt_data(ticker, today.date(), current_sentiment, current_attention, source="live")
            elif not Config.USE_SYNTHETIC_DB:
                try:
                    history_df.to_parquet(self._get_alt_cache_path(ticker))
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

    def get_company_profile(self, ticker: str) -> dict:
        """
        Fetches profile (Fundamental metrics + Sector/Industry).
        Updates DB with metadata if available.
        """
        profile = {}
        
        # 0. Try DB First (Optimization)
        if Config.USE_SYNTHETIC_DB and self.db:
            try:
                # We can reuse fetch_key_metrics logic via DB or check dim_assets
                # fetch_key_metrics returns {pe, market_cap, sector, industry, name}
                db_profile = self.db.fetch_key_metrics(ticker)
                if db_profile and db_profile.get('name'):
                    db_profile["_source"] = "🟠 CACHE (DB)"
                    return db_profile
            except Exception as e:
                pass

        # 1. Try Live (Preferred for profile data which changes rarely but needs to be accurate initially)
        if self.live_provider:
            try:
                print(f"🏢 Fetching Profile for {ticker}...")
                profile = self.live_provider.fetch_key_metrics(ticker)
                
                # Update DB
                if profile and self.db:
                   self.db.add_asset(
                       ticker, 
                       name=profile.get("name", ""), 
                       sector=profile.get("sector", ""), 
                       industry=profile.get("industry", "")
                   )
                if profile: profile["_source"] = "🟢 LIVE"
            except Exception as e:
                print(f"Profile Fetch Error: {e}")
        
        return profile
        
    def search_assets(self, query: str) -> list:
        """
        Search for assets matching a query.
        """
        if Config.USE_SYNTHETIC_DB:
            return self.provider.search_assets(query)
            
        return self.provider.search_assets(query)
        
    def get_fundamentals(self, ticker: str, allow_fallback: bool = True) -> dict:
        """
        Fetch fundamental metrics like P/E.
        """
        # Special Case: Metadata tickers
        if ticker.startswith("$"):
            return {'pe_ratio': 0.0, 'market_cap': 0.0}

        if Config.USE_SYNTHETIC_DB and self.db:
             data = self.db.fetch_key_metrics(ticker)
             data["_source"] = "🟠 CACHE (DB)"
             
             # If we disallow fallback (e.g. for fast dashboard), return what we have
             if not allow_fallback:
                 return data

             # If valid data found (pe_ratio > 0 is a heuristic, key check better)
             if data.get('market_cap', 0) > 0 or data.get('pe_ratio', 0) > 0:
                 return data
             
             # Fallback
             try:
                data = {}
                # Chain: AV -> YF
                if Config.ALPHA_VANTAGE_API_KEY:
                    try:
                        data = AlphaVantageProvider().fetch_key_metrics(ticker)
                    except: 
                        pass
                
                # If AV gave nothing useful, try YF
                if not data.get('pe_ratio') and not data.get('market_cap'):
                    try:
                        data = YFinanceProvider().fetch_key_metrics(ticker)
                    except:
                        pass
                
                # Save
                if data:
                    # Save to DB if provider supports it, or direct to DB if available
                    if hasattr(self.provider, 'save_fundamentals'):
                        self.provider.save_fundamentals(ticker, data)
                    elif self.db:
                        self.db.save_fundamentals(ticker, data)
                    data["_source"] = "🟢 LIVE"
                    return data
             except Exception as e:
                print(f"Fund Fallback Error: {e}")
                return {'pe_ratio': 0.0}

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
