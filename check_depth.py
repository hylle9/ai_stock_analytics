from src.data.db_manager import DBManager
import pandas as pd

# Connect via Manager
db = DBManager(read_only=True)
conn = db.get_connection()

print("Connected via DBManager.")

# List tables to be sure
print("Tables:", conn.execute("SHOW TABLES").fetchall())

# Check TSLA Alt Data
print(f"\n--- TSLA Alt Data ---")
try:
    df = conn.execute(f"SELECT * FROM fact_alt_data WHERE ticker='TSLA' ORDER BY date DESC LIMIT 5").df()
    print(df)
except Exception as e:
    print(f"Error querying TSLA Alt Data: {e}")
        
conn.close()
