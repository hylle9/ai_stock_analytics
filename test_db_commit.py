import sys
import os
import duckdb

# Add src to path
sys.path.append(os.getcwd())

from src.data.db_manager import DBManager, Config

# Fake config
Config.USE_SYNTHETIC_DB = True
Config.DATA_CACHE_DIR = "data_test_lock"

def test_persistence():
    print("Testing DB Persistence...")
    db = DBManager(read_only=False)
    
    # 1. Write
    con = db.get_connection()
    try:
        # Create Table if not exists
        con.execute("CREATE TABLE IF NOT EXISTS test_persist (id INTEGER, val TEXT)")
        con.execute("DELETE FROM test_persist")
        con.execute("INSERT INTO test_persist VALUES (1, 'saved')")
        print("Inserted data.")
    except Exception as e:
        print(f"Write Error: {e}")
    finally:
        con.close() # Closes cursor
        
    # 2. Read (Same Process)
    con2 = db.get_connection()
    res = con2.execute("SELECT * FROM test_persist").fetchall()
    print(f"Read (Same Process): {res}")
    con2.close()
    
    if not res:
        print("FAIL: Data not readable in same process!")
        return

    # 3. Read (New Manager / Simulating Reconnect)
    # Since Connection is Singleton, new Manager shares it.
    db2 = DBManager(read_only=False)
    con3 = db2.get_connection()
    res3 = con3.execute("SELECT * FROM test_persist").fetchall()
    print(f"Read (Shared Manager): {res3}")
    con3.close()
    
    # 4. Read (New Process - simulated by closing connection explicitly)
    # Force close singleton
    if DBManager._SHARED_CONNECTION:
        DBManager._SHARED_CONNECTION.close()
        DBManager._SHARED_CONNECTION = None
        print("Closed Singleton Connection.")
        
    # Re-open
    db3 = DBManager(read_only=False)
    con4 = db3.get_connection()
    res4 = con4.execute("SELECT * FROM test_persist").fetchall()
    print(f"Read (After Reopen): {res4}")
    con4.close()
    
    if not res4:
         print("FAIL: Data NOT persisted to disk after connection close!")
    else:
         print("SUCCESS: Data persisted.")

    # Cleanup
    import shutil
    if os.path.exists("data_test_lock"):
        shutil.rmtree("data_test_lock")

if __name__ == "__main__":
    test_persistence()
