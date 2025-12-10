from src.data.providers import BaseDataProvider
from src.data.db_manager import DBManager
import pandas as pd
import datetime

class DuckDBProvider(BaseDataProvider):
    """
    Data Provider that reads from the local DuckDB instance.
    Used for 'Synthetic Mode'.
    """
    def __init__(self, read_only: bool = False):
        self.db = DBManager(read_only=read_only)
    
    def fetch_ohlcv(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        """
        Fetch OHLCV from fact_market_data.
        Respects period by filtering relative to the latest available date for the ticker.
        """
        con = self.db.get_connection()
        try:
            # Map period to interval
            interval_map = {
                "1mo": "INTERVAL 30 DAY",
                "3mo": "INTERVAL 90 DAY",
                "6mo": "INTERVAL 180 DAY",
                "1y": "INTERVAL 1 YEAR",
                "2y": "INTERVAL 2 YEAR",
                "5y": "INTERVAL 5 YEAR",
                "max": None
            }
            # Default to 2y if unknown, unless period is int (limit) from older code? logic check
            interval = interval_map.get(period, "INTERVAL 2 YEAR")
            
            if period == "max":
                query = """
                    SELECT open, high, low, close, volume, date
                    FROM fact_market_data
                    WHERE ticker = ?
                    ORDER BY date ASC
                """
                df = con.execute(query, [ticker]).fetchdf()
            else:
                # Dynamic filtering relative to latest date (supports future synthetic dates)
                query = f"""
                    WITH max_d AS (SELECT MAX(date) as mx FROM fact_market_data WHERE ticker = ?)
                    SELECT open, high, low, close, volume, date
                    FROM fact_market_data, max_d
                    WHERE ticker = ?
                    AND date >= (max_d.mx - {interval})
                    ORDER BY date ASC
                """
                df = con.execute(query, [ticker, ticker]).fetchdf()
            
            if df.empty:
                return pd.DataFrame()
                
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df
        except Exception as e:
            print(f"DB Fetch OHLCV Error: {e}")
            return pd.DataFrame()
        finally:
            con.close()

    def fetch_key_metrics(self, ticker: str) -> dict:
        con = self.db.get_connection()
        try:
            # Get latest
            query = """
                SELECT pe_ratio, market_cap, eps
                FROM fact_fundamentals
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            """
            result = con.execute(query, [ticker]).fetchone()
            if result:
                return {
                    'pe_ratio': result[0],
                    'market_cap': result[1],
                    'eps': result[2]
                }
            return {'pe_ratio': 0.0}
        finally:
            con.close()

    def fetch_news(self, ticker: str, limit: int = 10) -> list:
        con = self.db.get_connection()
        try:
            query = """
                SELECT title, publisher, link, publish_time, sentiment_score
                FROM fact_news
                WHERE ticker = ?
                ORDER BY publish_time DESC
                LIMIT ?
            """
            results = con.execute(query, (ticker, limit)).fetchall()
            
            news = []
            for r in results:
                news.append({
                    'title': r[0],
                    'publisher': r[1],
                    'link': r[2],
                    'providerPublishTime': r[3],
                    'sentiment_score': r[4]
                })
            return news
        finally:
            con.close()

    def save_news(self, ticker: str, news_items: list):
        if not news_items: return
        con = self.db.get_connection()
        try:
            self.add_asset(ticker)
            import hashlib
            
            data_to_insert = []
            for item in news_items:
                # Generate unique ID
                raw_id = f"{ticker}_{item.get('link', '')}_{item.get('title', '')}"
                nid = hashlib.md5(raw_id.encode()).hexdigest()
                
                data_to_insert.append((
                    nid,
                    ticker,
                    item.get('title'),
                    item.get('publisher'),
                    item.get('link'),
                    item.get('providerPublishTime', 0),
                    item.get('sentiment_score', 0.0)
                ))
            
            con.executemany("""
                INSERT OR IGNORE INTO fact_news (news_id, ticker, title, publisher, link, publish_time, sentiment_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, data_to_insert)
            print(f"✅ Saved {len(data_to_insert)} news items to DB for {ticker}")
        except Exception as e:
            print(f"DB Save Error (News): {e}")
        finally:
            con.close()

    def fetch_sentiment(self, ticker: str) -> float:
        con = self.db.get_connection()
        try:
            query = """
                SELECT sentiment_score
                FROM fact_alt_data
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            """
            result = con.execute(query, [ticker]).fetchone()
            return result[0] if result else 0.0
        finally:
            con.close()

    def save_alt_data(self, ticker: str, date_obj, sentiment: float, attention: float, source: str = "synthetic"):
        con = self.db.get_connection()
        try:
            self.add_asset(ticker)
            d = date_obj.strftime('%Y-%m-%d') if hasattr(date_obj, 'strftime') else date_obj
            con.execute("INSERT OR REPLACE INTO fact_alt_data (ticker, date, sentiment_score, web_attention) VALUES (?, ?, ?, ?)", 
                       (ticker, d, sentiment, attention))
        except Exception as e:
            print(f"DB Save Error (Alt): {e}")
        finally:
            con.close()

    def fetch_alt_history(self, ticker: str, days: int = 30) -> pd.DataFrame:
        con = self.db.get_connection()
        try:
            query = """
                SELECT date, sentiment_score, web_attention
                FROM fact_alt_data 
                WHERE ticker = ? 
                ORDER BY date DESC
                LIMIT ?
            """
            df = con.execute(query, (ticker, days)).fetchdf()
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
            return df
        finally:
            con.close()
            
    def fetch_attention(self, ticker: str) -> float:
        """Compatibility for StockTwitsProvider behavior if needed"""
        con = self.db.get_connection()
        try:
            query = """
                SELECT web_attention
                FROM fact_alt_data
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            """
            result = con.execute(query, [ticker]).fetchone()
            return result[0] if result else 0.0
        finally:
            con.close()
            
    def search_assets(self, query: str) -> list:
        con = self.db.get_connection()
        try:
            sql = """
                SELECT ticker, name, sector 
                FROM dim_assets 
                WHERE ticker ILIKE ? OR name ILIKE ?
                LIMIT 10
            """
            pattern = f"%{query}%"
            results = con.execute(sql, [pattern, pattern]).fetchall()
            return [{"ticker": r[0], "name": r[1], "sector": r[2]} for r in results]
        finally:
            con.close()

    def get_asset_details(self, ticker: str) -> dict:
        con = self.db.get_connection()
        try:
            sql = "SELECT ticker, name, sector, description FROM dim_assets WHERE ticker = ?"
            r = con.execute(sql, [ticker]).fetchone()
            if r:
                return {"ticker": r[0], "name": r[1], "sector": r[2], "summary": r[3]}
            return {}
        finally:
            con.close()
            
    def get_latest_dates_map(self) -> dict:
        """
        Returns a dict of {ticker: max_date_str} for all assets.
        Efficient batch query.
        """
        con = self.db.get_connection()
        try:
            query = "SELECT ticker, MAX(date) as mx FROM fact_market_data GROUP BY ticker"
            df = con.execute(query).fetchdf()
            if df.empty: return {}
            # Convert to dict {ticker: 'YYYY-MM-DD'}
            # Ensure date is string
            return dict(zip(df['ticker'], df['mx'].astype(str)))
        except Exception as e:
            print(f"Error fetching latest dates map: {e}")
            return {}
        finally:
            con.close()

    def save_ohlcv(self, ticker: str, df: pd.DataFrame, source: str = "synthetic"):
        """
        Upsert OHLCV data into fact_market_data.
        """
        if df.empty:
            return
            
        con = self.db.get_connection()
        try:
            # Ensure asset exists first (FK constraint)
            self.add_asset(ticker)
            
            # Prepare data
            records = []
            for index, row in df.iterrows():
                # Handle timezone if present
                dt = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else index
                
                records.append((
                    ticker, 
                    dt,
                    float(row.get('open', 0)), 
                    float(row.get('high', 0)), 
                    float(row.get('low', 0)), 
                    float(row.get('close', 0)), 
                    int(row.get('volume', 0))
                ))
            
            # Upsert
            con.executemany("""
                INSERT OR REPLACE INTO fact_market_data (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)
            
        except Exception as e:
            print(f"DB Save Error (OHLCV): {e}")
        finally:
            con.close()
            
    def fetch_ohlcv(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        con = self.db.get_connection()
        try:
            # Convert period to interval (simplified)
            period_map = {
                "1mo": "30 days", "3mo": "90 days", "6mo": "180 days",
                "1y": "1 year", "2y": "2 years", "5y": "5 years", "max": "50 years"
            }
            period_sql = period_map.get(period, "1 year")

            # Dynamic start date relative to available data
            # This ensures '1y' means 'Last 1 year of data' not 'Today - 1 year' (in case of synthetic future data)
            query = f"""
                SELECT date, open, high, low, close, volume
                FROM fact_market_data 
                WHERE ticker = ? 
                AND date >= (SELECT MAX(date) - INTERVAL '{period_sql}' FROM fact_market_data WHERE ticker = ?)
                ORDER BY date ASC
            """
            
            df = con.execute(query, (ticker, ticker)).fetchdf()
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            return df
        finally:
            con.close()

    def save_fundamentals(self, ticker: str, data: dict):
        con = self.db.get_connection()
        try:
            self.add_asset(ticker)
            today = datetime.date.today()
            con.execute("INSERT OR IGNORE INTO fact_fundamentals VALUES (?, ?, ?, ?, ?)", 
                       (ticker, today, data.get('pe_ratio', 0), data.get('market_cap', 0), data.get('eps', 0)))
        except Exception as e:
            print(f"DB Save Error (Fund): {e}")
        finally:
            con.close()

    def add_asset(self, ticker: str, name: str = "", sector: str = "", industry: str = ""):
         con = self.db.get_connection()
         try:
             # Update metadata if provided
             if name or sector or industry:
                 updates = []
                 params = []
                 if name: 
                     updates.append("name = ?")
                     params.append(name)
                 if sector: 
                     updates.append("sector = ?")
                     params.append(sector)
                 if industry:
                     updates.append("industry = ?")
                     params.append(industry)
                     
                 if updates:
                     sql = "UPDATE dim_assets SET " + ", ".join(updates) + " WHERE ticker = ?"
                     params.append(ticker)
                     con.execute(sql, params)
             
             # Ensure existence
             con.execute("INSERT OR IGNORE INTO dim_assets (ticker, name, sector, industry) VALUES (?, ?, ?, ?)", 
                        (ticker, name or ticker, sector or "Unknown", industry or "Unknown"))
         finally:
             con.close()

    def fetch_batch_ohlcv(self, tickers: list[str], period: str = "2y") -> dict:
        """
        Efficiently fetch data for multiple tickers in ONE query.
        Returns: {ticker: pd.DataFrame}
        """
        if not tickers:
            return {}
            
        # Calc date
        days_map = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 20000}
        days = days_map.get(period, 730)
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).date()
        
        con = self.db.get_connection()
        try:
            # SQL IN Clause construction
            ticker_list_str = ", ".join([f"'{t}'" for t in tickers])
            query = f"""
                SELECT * FROM fact_market_data 
                WHERE ticker IN ({ticker_list_str}) 
                ORDER BY ticker, date ASC
            """
            
            # Execute
            big_df = con.execute(query).fetchdf()
            
            if big_df.empty:
                return {}
            
            # Post-process: Split by ticker
            result = {}
            for t in tickers:
                # Optimized filtering
                sub_df = big_df[big_df['ticker'] == t].copy()
                if not sub_df.empty:
                    sub_df['date'] = pd.to_datetime(sub_df['date'])
                    sub_df.set_index('date', inplace=True)
                    result[t] = sub_df
            
            return result
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Error in batch fetch: {e}")
            return {}
        finally:
            con.close()

    def get_latest_date(self, ticker: str) -> str:
        """
        Returns the latest date (YYYY-MM-DD) available for a ticker.
        Returns None if no data exists.
        """
        con = self.db.get_connection()
        try:
            res = con.execute("SELECT MAX(date) FROM fact_market_data WHERE ticker=?", (ticker,)).fetchone()
            if res and res[0]:
                # res[0] is date object
                return res[0].strftime("%Y-%m-%d")
            return None
        except Exception as e:
             print(f"DB Get Latest Date Error: {e}")
             return None
        finally:
            con.close()

    def get_asset_origin(self, ticker: str) -> str:
        """
        Returns the retrieval_origin for a ticker (e.g. 'RBRS', 'AIRS').
        Returns 'UNKNOWN' if not found.
        """
        con = self.db.get_connection()
        try:
            res = con.execute("SELECT retrieval_origin FROM dim_assets WHERE ticker=?", (ticker,)).fetchone()
            if res and res[0]:
                return res[0]
            return "UNKNOWN"
        except Exception as e:
            # print(f"DB Get Origin Error: {e}")
            return "UNKNOWN"
        finally:
            con.close()
