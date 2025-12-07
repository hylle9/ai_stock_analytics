import duckdb
import os
from typing import Optional
from src.utils.config import Config

class DBManager:
    """
    Manages DuckDB connection and schema initialization.
    """
    DB_PATH = os.path.join(Config.DATA_CACHE_DIR, "market_data.duckdb")

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_PATH
        # Ensure dir exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.initialize_db()

    def get_connection(self):
        """Returns a connection to the DuckDB instance."""
        return duckdb.connect(self.db_path)

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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

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
