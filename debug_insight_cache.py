import sys
import os
import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.utils.config import Config
Config.USE_SYNTHETIC_DB = True
Config.DATA_STRATEGY = "SYNTHETIC"

from src.analytics.insights import InsightManager
from src.data.db_manager import DBManager

def debug_cache():
    print("--- Debugging Insight Cache ---")
    
    ticker = "DEBUG_GOOG"
    content = "This is a test insight."
    rpt_type = "technical"
    
    im = InsightManager()
    
    # 1. Clear existing (manual SQL)
    print("1. Clearing old debug data...")
    con = im.db.get_connection()
    con.execute("DELETE FROM fact_ai_reports WHERE ticker = ?", (ticker,))
    im.db.commit()
    con.close()
    
    # 2. Save
    print("2. Saving new insight...")
    im.save_insight(ticker, content, rpt_type)
    
    # 3. Inspect Raw DB
    print("3. Inspecting Raw DB Row...")
    con = im.db.get_connection()
    rows = con.execute("SELECT * FROM fact_ai_reports WHERE ticker = ?", (ticker,)).fetchall()
    print(f"Raw Rows: {rows}")
    con.close()
    
    if not rows:
        print("❌ CRITICAL: Row not found in DB after save!")
        return

    # 4. Try Load
    print("4. Attempting Load via get_todays_insight...")
    loaded = im.get_todays_insight(ticker, rpt_type, valid_days=1)
    
    if loaded == content:
        print("✅ SUCCESS: Insight loaded correctly.")
    else:
        print(f"❌ FAIL: Loaded content is '{loaded}' (Expected '{content}')")
        
        # Debug Date Logic
        stored_date = rows[0][2] # Index 2 is date based on INSERT
        print(f"Stored Date Type: {type(stored_date)}")
        print(f"Stored Date Value: {stored_date}")
        
        today = datetime.datetime.now().date()
        print(f"Today: {today}")
        
        if hasattr(stored_date, 'date'): # if datetime
             print(f"Stored.date(): {stored_date.date()}")

if __name__ == "__main__":
    debug_cache()
