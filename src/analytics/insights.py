
import json
import os
from datetime import datetime

from src.utils.config import Config
if Config.USE_SYNTHETIC_DB:
    pass

class InsightManager:
    """
    Manages persistence for AI insights via JSON or DuckDB.
    """
    STORAGE_PATH = "data/daily_ai_insights.json"
    
    def __init__(self):
        self.cache = {}
        if Config.USE_SYNTHETIC_DB:
             from src.data.db_manager import DBManager
             self.db = DBManager()
        else:
             self.db = None
        
        if not Config.USE_SYNTHETIC_DB:
            self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    self.cache = json.load(f)
            except Exception as e:
                print(f"Error loading insight cache: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
            # Atomic save
            temp_path = self.STORAGE_PATH + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.cache, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.STORAGE_PATH)
        except Exception as e:
            print(f"Error saving insight cache: {e}")

    def get_todays_insight(self, ticker: str, report_type: str = "technical", valid_days: int = 1) -> str:
        """
        Returns cached insight if within valid_days.
        """
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        
        if Config.USE_SYNTHETIC_DB and self.db:
            try:
                con = self.db.get_connection()
                # DuckDB Date logic: date >= today - valid_days
                # Simplification: Just get the latest report for this ticker/type
                query = """
                    SELECT content, date 
                    FROM fact_ai_reports 
                    WHERE ticker = ? AND report_type = ? 
                    ORDER BY date DESC 
                    LIMIT 1
                """
                res = con.execute(query, (ticker, report_type)).fetchone()
                con.close()
                
                if res:
                    content, db_date = res
                    # db_date is usually datetime.date object
                    # Check validity
                    if isinstance(db_date, str):
                        delta = (today - datetime.strptime(db_date, "%Y-%m-%d")).days
                    else:
                        delta = (today.date() - db_date).days
                        
                    if delta < valid_days:
                        return content
                return None
            except Exception as e:
                print(f"DB Read Error: {e}")
                return None

        # --- JSON Fallback ---
        key = ticker if report_type == "technical" else f"{ticker}_{report_type}"
        
        if key in self.cache:
            entry = self.cache[key]
            entry_date_str = entry.get("date")
            
            if valid_days == 1:
                # Strict today check (optimized)
                if entry_date_str == today_str:
                    return entry.get("content")
            else:
                # Retention Check
                try:
                    entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d")
                    if (today - entry_date).days < valid_days:
                        return entry.get("content")
                except ValueError:
                    pass
                    
        return None

    def save_insight(self, ticker: str, content: str, report_type: str = "technical"):
        """
        Saves the insight.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if Config.USE_SYNTHETIC_DB and self.db:
            try:
                con = self.db.get_connection()
                import uuid
                rid = str(uuid.uuid4())
                model_used = 'gemini-2.5-flash' 
                
                con.execute("""
                    INSERT INTO fact_ai_reports (report_id, ticker, date, report_type, content, model_used)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (rid, ticker, datetime.now().date(), report_type, content, model_used))
                con.close()
                print(f"✅ Saved AI Insight to DB for {ticker}")
                return
            except Exception as e:
                print(f"DB Write Error: {e}")
        
        # --- JSON Fallback ---
        key = ticker if report_type == "technical" else f"{ticker}_{report_type}"
        
        self.cache[key] = {
            "date": today_str,
            "content": content
        }
        self._save_cache()
