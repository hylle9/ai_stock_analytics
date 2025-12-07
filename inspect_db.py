from src.data.db_manager import DBManager
from src.utils.config import Config

Config.USE_SYNTHETIC_DB = True
db = DBManager()
con = db.get_connection()
try:
    print("--- dim_assets Summary ---")
    res = con.execute("SELECT sector, count(*) as count FROM dim_assets GROUP BY sector").fetchdf()
    print(res)
    
    print("\n--- Unknown Sector Assets ---")
    res = con.execute("SELECT ticker, name, sector, industry FROM dim_assets WHERE sector='Unknown' LIMIT 10").fetchdf()
    print(res)
    
    print("\n--- AMZN ---")
    res = con.execute("SELECT ticker, name, sector, industry FROM dim_assets WHERE ticker='AMZN'").fetchdf()
    print(res)
finally:
    con.close()
