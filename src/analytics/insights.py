import json
import os
from datetime import datetime

class InsightManager:
    """
    Manages persistence for AI insights to ensure Gemini is only called 
    once per day per ticker.
    """
    STORAGE_PATH = "data/daily_ai_insights.json"
    
    def __init__(self):
        self.cache = {}
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
        Default 1 means "Today Only".
        """
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        
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
        Saves the insight for the ticker with today's date.
        Overwrites any previous data for this ticker/type.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Backward compatibility
        key = ticker if report_type == "technical" else f"{ticker}_{report_type}"
        
        self.cache[key] = {
            "date": today_str,
            "content": content
        }
        self._save_cache()
