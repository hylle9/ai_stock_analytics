from src.utils.config import Config
Config.USE_SYNTHETIC_DB = True
from src.data.db_manager import DBManager
from src.analytics.robo_advisor import RoboAdvisor
import pandas as pd

def debug():
    db = DBManager(read_only=True)
    con = db.get_connection()
    
    print("--- DB INSPECTION ---")
    
    # 1. Count
    count = con.execute("SELECT COUNT(*) FROM fact_market_data").fetchone()[0]
    print(f"Total Rows in fact_market_data: {count}")
    
    if count == 0:
        print("❌ TABLE IS EMPTY!")
        return

    # 2. Check AAPL
    print("\n--- AAPL DATA ---")
    try:
        rows = con.execute("SELECT date, close FROM fact_market_data WHERE ticker='AAPL' ORDER BY date DESC LIMIT 5").fetchdf()
        print(rows)
    except Exception as e:
        print(f"Error fetching AAPL: {e}")
        
    # 3. Check Query Logic (Manually)
    print("\n--- QUERY TEST ---")
    try:
        query = """
            SELECT 
                ticker, 
                date, 
                close,
                AVG(close) OVER (
                    PARTITION BY ticker 
                    ORDER BY date 
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) as sma20
            FROM fact_market_data
            WHERE ticker='AAPL'
            ORDER BY date DESC
            LIMIT 5
        """
        df = con.execute(query).fetchdf()
        print("Manual SMA20 Test:")
        print(df)
    except Exception as e:
        print(f"Query Error: {e}")

    # 4. Run Robo Advisor
    print("\n--- ROBO ADVISOR TEST ---")
    robo = RoboAdvisor()
    res = robo.scan_market(portfolio_tickers=['AAPL', 'MSFT'])
    print(f"Rising: {len(res.get('rising', []))}")
    print(f"Falling: {len(res.get('falling', []))}")
    print(f"New Opps: {len(res.get('new_opps', []))}")
    
    if res.get('rising'):
        print("Example Rising:", res['rising'][0])

if __name__ == "__main__":
    debug()
