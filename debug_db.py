
import duckdb
import pandas as pd
import json

db_path = "data/raw/market_data.duckdb"

try:
    con = duckdb.connect(db_path, read_only=True)
    print("Connected to DB.")
    
    ticker = "GOOG"
    
    print(f"\n--- Recent Interactions for {ticker} ---")
    rows = con.execute(f"SELECT * FROM fact_user_interactions WHERE ticker='{ticker}' ORDER BY timestamp DESC LIMIT 10").fetchall()
    
    columns = ["id", "ticker", "type", "timestamp", "metadata"]
    for r in rows:
        print(r)
        
    print("\n--- Recent Interactions for AAPL ---")
    rows = con.execute(f"SELECT * FROM fact_user_interactions WHERE ticker='AAPL' ORDER BY timestamp DESC LIMIT 10").fetchall()
    for r in rows:
        print(r)

    con.close()
except Exception as e:
    print(f"Error: {e}")
