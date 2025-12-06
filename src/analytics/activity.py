import json
import os
from datetime import datetime
from collections import defaultdict, Counter

class ActivityTracker:
    """
    Tracks user activity (views) and pressure scores to surface 'Favorite Stocks'.
    """
    STORAGE_PATH = "data/user_activity.json"

    def __init__(self):
        # Default schema
        self.data = {
            "likes": [],     # List of ticker strings
            "history": {}    # Date -> Ticker -> Data
        }
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    loaded = json.load(f)
                    
                # Schema Migration: Check if root keys are dates (Old Schema)
                is_old_schema = any(k.startswith("20") for k in loaded.keys())
                
                if is_old_schema:
                    print("migrating activity log to new schema...")
                    self.data["history"] = loaded
                    self.data["likes"] = []
                    self._save_data()
                else:
                    # New Schema
                    self.data = loaded
                    # Ensure keys exist
                    if "likes" not in self.data: self.data["likes"] = []
                    if "history" not in self.data: self.data["history"] = {}
                    
            except Exception as e:
                print(f"Error loading user activity: {e}")

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
            # Atomic save
            temp_path = self.STORAGE_PATH + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.STORAGE_PATH)
        except Exception as e:
            print(f"Error saving user activity: {e}")

    def toggle_like(self, ticker: str):
        """Toggles the liked state of a ticker."""
        if ticker in self.data["likes"]:
            self.data["likes"].remove(ticker)
        else:
            self.data["likes"].append(ticker)
        self._save_data()
        
    def is_liked(self, ticker: str) -> bool:
        return ticker in self.data["likes"]

    def get_liked_stocks(self) -> list:
        """
        Returns list of liked stocks with their latest pressure score.
        """
        results = []
        history = self.data["history"]
        sorted_days = sorted(history.keys(), reverse=True)
        
        for ticker in self.data["likes"]:
            # Find latest score
            current_score = 0.0
            
            for day in sorted_days:
                if ticker in history[day]:
                    current_score = history[day][ticker]["score"]
                    break
            
            results.append({
                "ticker": ticker,
                "pressure_score": current_score,
                # We can calculate rising diff here too if needed, 
                # but for now just returning the object logic
                "rising_diff": self._calculate_rising_diff(ticker, history, sorted_days)
            })
            
        return results

    def _calculate_rising_diff(self, ticker, history, sorted_days):
        ticker_scores = []
        for day in sorted_days:
            if ticker in history[day]:
                ticker_scores.append(history[day][ticker]["score"])
        
        if not ticker_scores:
            return 0.0
            
        current_score = ticker_scores[0]
        # Prev 3
        hist_win = ticker_scores[1:4]
        if not hist_win:
            avg_prev = current_score
        else:
            avg_prev = sum(hist_win) / len(hist_win)
            
        return current_score - avg_prev

    def log_view(self, ticker: str, pressure_score: float):
        """
        Logs a view for a ticker on the current date, updating the pressure score.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        history = self.data["history"]
        
        if today not in history:
            history[today] = {}
        
        if ticker not in history[today]:
            history[today][ticker] = {
                "views": 0,
                "score": 0.0
            }
            
        # Update entry
        entry = history[today][ticker]
        entry["views"] += 1
        entry["score"] = float(pressure_score) # Store latest score for the day
        
        self._save_data()

    def get_rising_pressure_stocks(self, limit: int = 12) -> list:
        """
        Returns top viewed stocks sorted by 'Rising Diff Pressure'.
        Renamed from get_favorites to be more specific.
        """
        history = self.data["history"]
        
        # 1. Identify active days (days with at least one record)
        sorted_days = sorted(history.keys(), reverse=True)
        last_10_days = sorted_days[:10]
        
        if not last_10_days:
            return []
            
        # 2. Aggregate views for the pool
        view_counts = Counter()
        for day in last_10_days:
            for ticker, info in history[day].items():
                view_counts[ticker] += info.get("views", 0)
                
        # Get top 100 by views
        top_100_tickers = [t for t, _ in view_counts.most_common(100)]
        
        results = []
        
        for ticker in top_100_tickers:
            # 3. Calculate Scores
            # Get history of scores for this ticker across ALL active days (not just last 10)
            diff = self._calculate_rising_diff(ticker, history, sorted_days)
            
            # Get current score
            current_score = 0.0
            for day in sorted_days:
                if ticker in history[day]:
                    current_score = history[day][ticker]["score"]
                    break

            results.append({
                "ticker": ticker,
                "pressure_score": current_score,
                "rising_diff": diff
            })
            
        # 4. Sort by Rising Diff Descending
        results.sort(key=lambda x: x["rising_diff"], reverse=True)
        
        return results[:limit]
