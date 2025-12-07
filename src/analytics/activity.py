from src.utils.config import Config
if Config.USE_SYNTHETIC_DB:
    pass # deferred import
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
        if Config.USE_SYNTHETIC_DB:
             from src.data.db_manager import DBManager
             self.db = DBManager()
        else:
             self.db = None
        
        if not Config.USE_SYNTHETIC_DB:
            self._load_data()

    def _load_data(self):
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    loaded = json.load(f)
                is_old_schema = any(k.startswith("20") for k in loaded.keys())
                if is_old_schema:
                    self.data["history"] = loaded
                    self.data["likes"] = []
                    self._save_data()
                else:
                    self.data = loaded
                    if "likes" not in self.data: self.data["likes"] = []
                    if "history" not in self.data: self.data["history"] = {}
            except Exception as e:
                print(f"Error loading user activity: {e}")

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
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
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                row = con.execute("SELECT interaction_id FROM fact_user_interactions WHERE interaction_type='LIKE' AND ticker=?", (ticker,)).fetchone()
                if row:
                    con.execute("DELETE FROM fact_user_interactions WHERE interaction_type='LIKE' AND ticker=?", (ticker,))
                else:
                    import uuid
                    iid = str(uuid.uuid4())
                    # Ensure asset
                    con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (ticker,))
                    con.execute("INSERT INTO fact_user_interactions (interaction_id, ticker, interaction_type) VALUES (?, ?, 'LIKE')", (iid, ticker))
            except Exception as e:
                print(f"DB Like Error: {e}")
            finally:
                con.close()
            return

        if ticker in self.data["likes"]:
            self.data["likes"].remove(ticker)
        else:
            self.data["likes"].append(ticker)
        self._save_data()
        
    def is_liked(self, ticker: str) -> bool:
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                res = con.execute("SELECT 1 FROM fact_user_interactions WHERE interaction_type='LIKE' AND ticker=?", (ticker,)).fetchone()
                return bool(res)
            except:
                return False
            finally:
                con.close()
                
        return ticker in self.data["likes"]

    def get_liked_stocks(self) -> list:
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            results = []
            try:
                likes = con.execute("SELECT ticker FROM fact_user_interactions WHERE interaction_type='LIKE'").fetchall()
                for (t,) in likes:
                    # Fetch latest score from VIEW history
                    score_res = con.execute("""
                        SELECT metadata 
                        FROM fact_user_interactions 
                        WHERE ticker=? AND interaction_type='VIEW' 
                        ORDER BY timestamp DESC LIMIT 1
                    """, (t,)).fetchone()
                    
                    score = 0.0
                    if score_res:
                        try:
                            # DuckDB JSON might return string or object depending on driver version
                            s_data = score_res[0]
                            if isinstance(s_data, str):
                                meta = json.loads(s_data)
                                score = meta.get("score", 0.0)
                        except: pass
                        
                    results.append({"ticker": t, "pressure_score": score, "rising_diff": 0.0})
            except Exception as e:
                print(f"DB Get Likes Error: {e}")
            finally:
                con.close()
            return results

        results = []
        history = self.data["history"]
        sorted_days = sorted(history.keys(), reverse=True)
        
        for ticker in self.data["likes"]:
            current_score = 0.0
            for day in sorted_days:
                if ticker in history[day]:
                    current_score = history[day][ticker]["score"]
                    break
            results.append({
                "ticker": ticker,
                "pressure_score": current_score,
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
        hist_win = ticker_scores[1:4]
        if not hist_win:
            avg_prev = current_score
        else:
            avg_prev = sum(hist_win) / len(hist_win)
            
        return current_score - avg_prev

    def log_view(self, ticker: str, pressure_score: float):
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                 import uuid
                 iid = str(uuid.uuid4())
                 meta = json.dumps({"score": float(pressure_score)})
                 con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (ticker,))
                 con.execute("""
                    INSERT INTO fact_user_interactions (interaction_id, ticker, interaction_type, metadata)
                    VALUES (?, ?, 'VIEW', ?)
                 """, (iid, ticker, meta))
            except Exception as e:
                print(f"DB Log View Error: {e}")
            finally:
                con.close()
            return

        today = datetime.now().strftime("%Y-%m-%d")
        history = self.data["history"]
        
        if today not in history:
            history[today] = {}
        
        if ticker not in history[today]:
            history[today][ticker] = {
                "views": 0,
                "score": 0.0
            }
            
        entry = history[today][ticker]
        entry["views"] += 1
        entry["score"] = float(pressure_score) 
        self._save_data()

    def get_rising_pressure_stocks(self, limit: int = 12) -> list:
        if Config.USE_SYNTHETIC_DB and self.db:
            # Simplified: Just Get Top Viewed Recently
            con = self.db.get_connection()
            try:
                # Count views in last 7 days
                rows = con.execute("""
                    SELECT ticker, COUNT(*) as views 
                    FROM fact_user_interactions 
                    WHERE interaction_type='VIEW' 
                      AND timestamp > (CURRENT_DATE - INTERVAL 7 DAY)
                    GROUP BY ticker 
                    ORDER BY views DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
                
                results = []
                for (t, v) in rows:
                    # Get score
                    score_res = con.execute("""
                        SELECT metadata FROM fact_user_interactions 
                        WHERE ticker=? AND interaction_type='VIEW' 
                        ORDER BY timestamp DESC LIMIT 1
                    """, (t,)).fetchone()
                    score = 0.0
                    if score_res:
                        try:
                             meta = json.loads(score_res[0])
                             score = meta.get("score", 0.0)
                        except: pass
                    results.append({"ticker": t, "pressure_score": score, "rising_diff": 0.0})
                return results
            except Exception as e:
                print(f"DB Rising Stocks Error: {e}")
                return []
            finally:
                con.close()

        # ... JSON Logic ...
        history = self.data["history"]
        sorted_days = sorted(history.keys(), reverse=True)
        last_10_days = sorted_days[:10]
        
        if not last_10_days:
            return []
            
        view_counts = Counter()
        for day in last_10_days:
            for ticker, info in history[day].items():
                view_counts[ticker] += info.get("views", 0)
                
        top_100_tickers = [t for t, _ in view_counts.most_common(100)]
        results = []
        for ticker in top_100_tickers:
            diff = self._calculate_rising_diff(ticker, history, sorted_days)
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
        results.sort(key=lambda x: x["rising_diff"], reverse=True)
        return results[:limit]
