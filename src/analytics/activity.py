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
             # Try to init normally first
             try:
                 self.db = DBManager(read_only=False)
                 self.read_only = False
             except Exception:
                 # If locked, fallback to read-only
                 print("⚠️ ActivityTracker: DB Locked. Switching to Read-Only.")
                 self.db = DBManager(read_only=True)
                 self.read_only = True
        else:
             self.db = None
             self.read_only = False
        
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
        if self.read_only:
            print("⚠️ Read-Only Mode: Cannot toggle like.")
            return

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
                    # Fetch last 5 VIEW interactions for score history
                    scores_res = con.execute("""
                        SELECT metadata 
                        FROM fact_user_interactions 
                        WHERE ticker=? AND interaction_type='VIEW' 
                        ORDER BY timestamp DESC LIMIT 5
                    """, (t,)).fetchall()
                    
                    history_scores = []
                    for row in scores_res:
                        try:
                            s_data = row[0]
                            if isinstance(s_data, str):
                                meta = json.loads(s_data)
                                history_scores.append(meta.get("score", 0.0))
                        except: pass
                    
                    current_score = history_scores[0] if history_scores else 0.0
                    
                    # Calculate Trend Diff (Current - Avg of prev 3)
                    diff = 0.0
                    if len(history_scores) > 1:
                        prev_window = history_scores[1:4] # Up to 3 previous
                        if prev_window:
                            avg_prev = sum(prev_window) / len(prev_window)
                            diff = current_score - avg_prev
                            
                    results.append({"ticker": t, "pressure_score": current_score, "rising_diff": diff})
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
        if self.read_only: return

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
                    # Get history scores
                    scores_res = con.execute("""
                        SELECT metadata FROM fact_user_interactions 
                        WHERE ticker=? AND interaction_type='VIEW' 
                        ORDER BY timestamp DESC LIMIT 5
                    """, (t,)).fetchall()
                    
                    history_scores = []
                    for row in scores_res:
                        try:
                             s_data = row[0]
                             if isinstance(s_data, str):
                                 meta = json.loads(s_data)
                                 history_scores.append(meta.get("score", 0.0))
                        except: pass

                    current_score = history_scores[0] if history_scores else 0.0
                    
                    # Diff
                    diff = 0.0
                    if len(history_scores) > 1:
                        prev_window = history_scores[1:4]
                        if prev_window:
                            avg_prev = sum(prev_window) / len(prev_window)
                            diff = current_score - avg_prev
                            
                    results.append({"ticker": t, "pressure_score": current_score, "rising_diff": diff})
                
                # Sort by Momentum (Descending)
                results.sort(key=lambda x: x["rising_diff"], reverse=True)
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
    def update_ticker_metadata(self, ticker: str, metadata: dict):
        """
        Updates metadata (e.g. pressure score) for a ticker.
        """
        if self.read_only: return

        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                 import uuid
                 # We treat this as a 'SYSTEM_UPDATE' or a special VIEW to persist score
                 iid = str(uuid.uuid4())
                 meta_json = json.dumps(metadata)
                 
                 con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (ticker,))
                 con.execute("""
                    INSERT INTO fact_user_interactions (interaction_id, ticker, interaction_type, metadata)
                    VALUES (?, ?, 'VIEW', ?)
                 """, (iid, ticker, meta_json))
            except Exception as e:
                print(f"DB Metadata Update Error: {e}")
            finally:
                con.close()
            return

        # Simple JSON update
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.data["history"]: self.data["history"][today] = {}
        
        if ticker not in self.data["history"][today]:
             self.data["history"][today][ticker] = {"views": 0, "score": 0.0}
             
        if "score" in metadata:
            self.data["history"][today][ticker]["score"] = float(metadata["score"])
        
        self._save_data()

    def get_market_weather(self) -> dict:
        """
        Retrieves the global market weather status.
        Returns dict with keys: score, status, last_updated.
        """
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                # Retrieve from VIEW interaction for '$MARKET'
                res = con.execute("""
                    SELECT metadata 
                    FROM fact_user_interactions 
                    WHERE ticker='$MARKET' AND interaction_type='VIEW' 
                    ORDER BY timestamp DESC LIMIT 1
                """).fetchone()
                
                if res:
                    try:
                        return json.loads(res[0])
                    except: pass
            except Exception as e:
                print(f"DB Market Weather Error: {e}")
            finally:
                con.close()
            return {}

        # JSON Fallback
        today = datetime.now().strftime("%Y-%m-%d")
        history = self.data["history"]
        if today in history and "$MARKET" in history[today]:
            entry = history[today]["$MARKET"]
            # Reconstruct extra fields if stored in 'score' only?
            # DCS stores full dict in set_metadata, but JSON implementation 
            # in update_ticker_metadata only saved 'score' to 'score' field.
            # We need to check if update_ticker_metadata handles arbitrary keys for JSON.
            # Looking at code: it only saves 'score'. 
            # Let's adjust JSON return to be consistent if possible, or accept just score.
            return {"score": entry.get("score", 50.0), "status": "UNKNOWN"}
            
        return {}
