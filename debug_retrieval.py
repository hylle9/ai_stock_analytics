import sys
import os
# Force project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.utils.config import Config
from src.data.retrieval import StockRetrievalSystem
from src.data.db_manager import DBManager

def main():
    print("--- 🧪 Debugging Stock Retrieval System (Origin Check) ---")
    
    # 1. Setup Environment
    if "--live" in sys.argv:
        Config.USE_SYNTHETIC_DB = True 
        Config.DATA_STRATEGY = "LIVE"
    else:
        Config.USE_SYNTHETIC_DB = True
        Config.DATA_STRATEGY = "SYNTHETIC"
        
    print(f"Mode: {Config.DATA_STRATEGY}")
    
    # 2. Run Retrieval
    srs = StockRetrievalSystem()
    stats = srs.run_full_cycle(competitor_limit=3, news_limit=3, dry_run=False)
    
    # 3. Validation Output
    print("\n--- 📊 Results ---")
    print(f"RBRS: {len(stats['rbrs'])}")
    print(f"AIRS: {len(stats['airs'])}")
    print(f"NRRS: {len(stats['nrrs'])}")
    
    # 4. Check Origins in DB
    print("\n--- 🕵️‍♀️ DB Origin Check ---")
    db = DBManager()
    con = db.get_connection()
    try:
        # Check a sample from each bucket
        buckets = {
            "RBRS": stats['rbrs'][:3],
            "AIRS": stats['airs'][:3],
            "NRRS": stats['nrrs'][:3]
        }
        
        for origin, samples in buckets.items():
            for t in samples:
                row = con.execute("SELECT retrieval_origin FROM dim_assets WHERE ticker=?", (t,)).fetchone()
                val = row[0] if row else "MISSING"
                print(f"[{origin}] {t}: {val}")
                
    finally:
        con.close()

if __name__ == "__main__":
    main()
