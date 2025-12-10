
import duckdb
import pandas as pd
import json
import uuid
import time
from datetime import datetime

db_path = "data/raw/market_data.duckdb"

print(f"Testing DB Write to {db_path}...")

try:
    # 1. Try Read-Write Connection
    con = duckdb.connect(db_path, read_only=False)
    print("✅ ACQUIRED WRITE LOCK.")
    
    # Check GOOG history
    print("\n--- GOOG History (Before) ---")
    rows = con.execute("SELECT * FROM fact_user_interactions WHERE ticker='GOOG' ORDER BY timestamp DESC LIMIT 5").fetchall()
    for r in rows:
        print(r)

    # Insert Dummy View
    iid = str(uuid.uuid4())
    meta = json.dumps({"score": 61.03, "test_run": True})
    ticker = "GOOG"
    
    con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (ticker,))
    con.execute("""
        INSERT INTO fact_user_interactions (interaction_id, ticker, interaction_type, metadata)
        VALUES (?, ?, 'VIEW', ?)
    """, (iid, ticker, meta))
    
    print("\n✅ INSERTED TEST ROW (61.03).")
    
    con.close()
    print("Connection Closed.")
    
except Exception as e:
    print(f"\n❌ WRITE FAILED: {e}")

# Read Output Verification
try:
    con = duckdb.connect(db_path, read_only=True)
    print("\n--- GOOG History (After) ---")
    rows = con.execute("SELECT * FROM fact_user_interactions WHERE ticker='GOOG' ORDER BY timestamp DESC LIMIT 5").fetchall()
    for r in rows:
        print(r)
    con.close()
except:
    pass
