import duckdb
import os
from typing import Optional
from src.utils.config import Config

class DBManager:
    """
    Centralized database connection manager.
    Handles schema initialization and connection pooling.
    """
    DATA_DIR = Config.DATA_CACHE_DIR
    DB_PATH = os.path.join(DATA_DIR, "market_data.duckdb")
    _SCHEMA_INITIALIZED = False

    def __init__(self, read_only: bool = False):
        self.read_only = read_only
        os.makedirs(self.DATA_DIR, exist_ok=True)
        # Attempt to initialize schema only if not read-only and not already done
        if not self.read_only and not DBManager._SCHEMA_INITIALIZED:
            try:
                self.initialize_db()
                DBManager._SCHEMA_INITIALIZED = True
            except Exception as e:
                # If locked, it usually means another process is writing or holding the lock.
                # Use a soft warning, as schema might likely represent "already initialized"
                print(f"⚠️ DB Schema Init Skipped (Persistence Check): {e}")

    def get_connection(self):
        """Returns a new DuckDB connection."""
        return duckdb.connect(self.DB_PATH, read_only=self.read_only)

    def initialize_db(self):
        """Creates tables if they don't exist."""
        con = self.get_connection()
        try:
            # 1. Assets Dimension
            con.execute("""
                CREATE TABLE IF NOT EXISTS dim_assets (
                    ticker VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    sector VARCHAR,
                    industry VARCHAR,
                    description TEXT,
                    retrieval_origin VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Auto-Migration: checking if column exists (simple try/catch or checks)
            try:
                con.execute("ALTER TABLE dim_assets ADD COLUMN retrieval_origin VARCHAR")
            except:
                pass # Already exists


            # 1.5 Competitors Junction
            con.execute("""
                CREATE TABLE IF NOT EXISTS dim_competitors (
                    ticker_a VARCHAR,
                    ticker_b VARCHAR,
                    reason VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ticker_a, ticker_b),
                    FOREIGN KEY (ticker_a) REFERENCES dim_assets(ticker),
                    FOREIGN KEY (ticker_b) REFERENCES dim_assets(ticker)
                );
            """)
            
            # Migration for existing DBs (Fix for Infinite AI Loop)
            try:
                con.execute("ALTER TABLE dim_competitors ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except:
                pass 
            
            # Backfill nulls
            try:
                con.execute("UPDATE dim_competitors SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            except: 
                pass

            # 2. Market Data Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_market_data (
                    ticker VARCHAR,
                    date DATE,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume BIGINT,
                    PRIMARY KEY (ticker, date),
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 3. Fundamentals Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_fundamentals (
                    ticker VARCHAR,
                    date DATE,
                    pe_ratio DOUBLE,
                    market_cap BIGINT,
                    eps DOUBLE,
                    PRIMARY KEY (ticker, date),
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 4. Alternative Data Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_alt_data (
                    ticker VARCHAR,
                    date DATE,
                    sentiment_score DOUBLE,
                    web_attention DOUBLE,
                    PRIMARY KEY (ticker, date),
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 5. AI Reports Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_ai_reports (
                    report_id VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    date DATE,
                    report_type VARCHAR,
                    content TEXT,
                    model_used VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 5.5 News Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_news (
                    news_id VARCHAR PRIMARY KEY, -- Hash of link or title
                    ticker VARCHAR,
                    title VARCHAR,
                    publisher VARCHAR,
                    link VARCHAR,
                    publish_time BIGINT,
                    sentiment_score DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 6. User Activity Fact
            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_user_interactions (
                    interaction_id VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    interaction_type VARCHAR, -- 'VIEW', 'LIKE'
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON,
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)

            # 7. Portfolios & Holdings
            con.execute("""
                CREATE TABLE IF NOT EXISTS dim_portfolios (
                    portfolio_id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    status VARCHAR,
                    cash DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            con.execute("""
                CREATE TABLE IF NOT EXISTS fact_holdings (
                    portfolio_id VARCHAR,
                    ticker VARCHAR,
                    quantity DOUBLE,
                    avg_buy_price DOUBLE,
                    PRIMARY KEY (portfolio_id, ticker),
                    FOREIGN KEY (portfolio_id) REFERENCES dim_portfolios(portfolio_id),
                    FOREIGN KEY (ticker) REFERENCES dim_assets(ticker)
                );
            """)
            
        finally:
            con.close()

    def update_asset_origin(self, ticker: str, origin: str):
        """
        Updates the retrieval_origin for an asset. 
        Appends if already exists to allow multi-origin (e.g. "RBRS,AIRS").
        """
        con = self.get_connection()
        try:
            # Check existing
            current = con.execute("SELECT retrieval_origin FROM dim_assets WHERE ticker=?", (ticker,)).fetchone()
            new_origin = origin
            
            if current and current[0]:
                existing_parts = set(current[0].split(","))
                existing_parts.add(origin)
                # Keep sorted for consistency
                new_origin = ",".join(sorted(list(existing_parts)))
            
            # Upsert asset if not exists (minimal) then update
            con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (ticker,))
            con.execute("UPDATE dim_assets SET retrieval_origin=? WHERE ticker=?", (new_origin, ticker))
            
        except Exception as e:
            print(f"DB Origin Update Error: {e}")
        finally:
            con.close()
