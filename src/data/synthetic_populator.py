import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import uuid
import random
from src.data.db_manager import DBManager

class SyntheticPopulator:
    """
    Populates DuckDB with synthetic market data for testing.
    """
    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.con = self.db.get_connection()

    def generate_random_walk(self, start_price, days, volatility=0.02):
        """Generates a random price path."""
        returns = np.random.normal(0, volatility, days)
        price_path = start_price * np.exp(np.cumsum(returns))
        return price_path

    def populate_all(self, num_assets=50, days_history=730):
        print(f"Generating synthetic data for {num_assets} assets over {days_history} days...")
        
        # 1. Assets
        tickers = [f"SYN{i:03d}" for i in range(num_assets)]
        sectors = ["Technology", "Healthcare", "Finance", "Consumer Discretionary", "Energy"]
        
        assets_data = []
        for t in tickers:
            assets_data.append((
                t, 
                f"Synthetic Corp {t}", 
                random.choice(sectors), 
                "Software", 
                "A synthetic company for testing purposes."
            ))
            
        self.con.executemany("INSERT OR IGNORE INTO dim_assets (ticker, name, sector, industry, description) VALUES (?, ?, ?, ?, ?)", assets_data)
        
        # 2. Market Data & 3. Fundamentals & 4. Alt Data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_history)
        dates = pd.date_range(start_date, end_date)
        
        for t in tickers:
            # Price Path
            start_price = random.uniform(20, 500)
            prices = self.generate_random_walk(start_price, len(dates))
            
            # Market Data Batch
            market_rows = []
            fund_rows = []
            alt_rows = []
            
            for i, date in enumerate(dates):
                close = float(prices[i])
                open_p = close * random.uniform(0.98, 1.02)
                high = max(open_p, close) * random.uniform(1.0, 1.05)
                low = min(open_p, close) * random.uniform(0.95, 1.0)
                vol = int(random.uniform(100000, 5000000))
                
                market_rows.append((t, date.date(), open_p, high, low, close, vol))
                
                # Fundamentals (Only periodic updates usually, but we'll do daily for simplicity)
                if i % 30 == 0: # Monthly
                    pe = random.uniform(10, 50)
                    mcap = int(close * 10000000)
                    eps = close / pe
                    fund_rows.append((t, date.date(), pe, mcap, eps))
                    
                # Alt Data
                sent = np.sin(i / 10) * 0.8 + random.normalvariate(0, 0.1) # Cyclic sentiment
                att = abs(np.cos(i / 15)) * 100
                alt_rows.append((t, date.date(), max(-1, min(1, sent)), max(0, min(100, att))))

            self.con.executemany("INSERT OR IGNORE INTO fact_market_data VALUES (?, ?, ?, ?, ?, ?, ?)", market_rows)
            self.con.executemany("INSERT OR IGNORE INTO fact_fundamentals VALUES (?, ?, ?, ?, ?)", fund_rows)
            self.con.executemany("INSERT OR IGNORE INTO fact_alt_data VALUES (?, ?, ?, ?)", alt_rows)
            
            # 5. AI Reports (Sparse)
            if random.random() > 0.5:
                report_id = str(uuid.uuid4())
                report_content = f"**Deep Research for {t}**\n\nThis is a synthetic report generated for testing."
                self.con.execute(
                    "INSERT INTO fact_ai_reports (report_id, ticker, date, report_type, content, model_used) VALUES (?, ?, ?, ?, ?, ?)",
                    (report_id, t, end_date.date(), "deep_research_weekly", report_content, "synthetic-model")
                )

        print("Synthetic data population complete.")
        self.con.close()

if __name__ == "__main__":
    db = DBManager()
    populator = SyntheticPopulator(db)
    populator.populate_all()
