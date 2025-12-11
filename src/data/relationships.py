import json
import os
import google.generativeai as genai
from typing import List, Dict, Optional
from src.utils.config import Config

class RelationshipManager:
    """
    Manages relationship data for tickers (Sector, Industry, Competitors).
    Supports persistence and AI-driven expansion.
    """
    
    STORAGE_PATH = "data/sp500_gemini_expand.json"
    
    SEED_PATH = "src/data/sp500_seed.json"

# from src.data.db_manager import DBManager # Removed top level

class RelationshipManager:
    """
    Manages relationship data for tickers (Sector, Industry, Competitors).
    Supports persistence via DuckDB or JSON.
    """
    
    STORAGE_PATH = "data/sp500_gemini_expand.json"
    SEED_PATH = "src/data/sp500_seed.json"

    def __init__(self):
        self.database = {}
        
        if Config.USE_SYNTHETIC_DB:
            from src.data.db_manager import DBManager
            self.db = DBManager()
            self._sync_seed_to_db()
        else:
            self.db = None
            self._load_database()

    def _sync_seed_to_db(self):
        """Syncs seed data into DuckDB if needed."""
        if os.path.exists(self.SEED_PATH):
            try:
                with open(self.SEED_PATH, 'r') as f:
                    seed_data = json.load(f)
                
                con = self.db.get_connection()
                try:
                    # OPTIMIZATION: Check if data exists first!
                    # If dim_assets has > 50 rows, we assume seed is loaded.
                    # This prevents 14s init delay on every page load.
                    count = con.execute("SELECT COUNT(*) FROM dim_assets").fetchone()[0]
                    if count >= 50:
                         return
                    
                    for t, v in seed_data.items():
                        # Unpack
                        name = v.get("name", t)
                        sector = v.get("sector", "Unknown")
                        industry = v.get("industry", "Unknown")
                        
                        # Upsert Asset
                        con.execute("INSERT OR IGNORE INTO dim_assets (ticker, name, sector, industry) VALUES (?, ?, ?, ?)", 
                                   (t, name, sector, industry))
                                   
                        # Competitors
                        comps = v.get("competitors", [])
                        for c in comps:
                            # Verify competitor exists as asset (placeholder)
                            con.execute("INSERT OR IGNORE INTO dim_assets (ticker, name, sector) VALUES (?, ?, ?)", 
                                       (c, c, sector)) # Assume same sector for simplicity if unknown
                            
                            # Insert Link
                            con.execute("INSERT OR IGNORE INTO dim_competitors (ticker_a, ticker_b, reason) VALUES (?, ?, ?)",
                                       (t, c, "Seed Data"))
                finally:
                    con.close()
            except Exception as e:
                print(f"Error syncing seed to DB: {e}")

    def _load_database(self):
        # 1. Try to load persistent expansion (Gemini Data)
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    self.database = json.load(f)
            except Exception as e:
                print(f"Error loading relationships: {e}")
        
        # 2. Always sync with Seed (Golden Master)
        self._load_seed()

    def _load_seed(self):
        if os.path.exists(self.SEED_PATH):
            try:
                with open(self.SEED_PATH, 'r') as f:
                    seed_data = json.load(f)
                    for k, v in seed_data.items():
                        if k not in self.database:
                            self.database[k] = v
                        else:
                            self.database[k]["sector"] = v["sector"]
                            self.database[k]["industry"] = v["industry"]
                            if "competitors" in v and v["competitors"] and not self.database[k].get("competitors"):
                                self.database[k]["competitors"] = v["competitors"]
            except Exception as e:
                print(f"Error loading seed: {e}")
        
    def _save_database(self):
        try:
            os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
            temp_path = self.STORAGE_PATH + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.database, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.STORAGE_PATH)
        except Exception as e:
            print(f"Error saving DB: {e}")
    
    def get_info(self, ticker: str) -> Optional[Dict]:
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                r = con.execute("SELECT name, sector, industry FROM dim_assets WHERE ticker=?", (ticker,)).fetchone()
                if r:
                    return {
                        "name": r[0], 
                        "sector": r[1], 
                        "industry": r[2], 
                        "competitors": self.get_competitors(ticker)
                    }
                return None
            except:
                return None
            finally:
                con.close()
                
        return self.database.get(ticker)
        
    def get_competitors(self, ticker: str) -> List[str]:
        if Config.USE_SYNTHETIC_DB and self.db:
             con = self.db.get_connection()
             try:
                 res = con.execute("SELECT ticker_b FROM dim_competitors WHERE ticker_a=?", (ticker,)).fetchall()
                 return [x[0] for x in res]
             except:
                 return []
             finally:
                 con.close()
                 
        info = self.database.get(ticker)
        if info:
            return info.get("competitors", [])
        return []
        
    def get_industry_peers(self, ticker, limit=10) -> List[str]:
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                # Find industry of ticker
                r = con.execute("SELECT industry, sector FROM dim_assets WHERE ticker=?", (ticker,)).fetchone()
                if not r: 
                    print(f"❌ Asset {ticker} not found in dim_assets during peer lookup.")
                    return []
                ind, sec = r
                print(f"🔍 Peer Lookup for {ticker}: Sector='{sec}', Industry='{ind}'")
                
                # Find others in same industry
                peers_query = """
                    SELECT ticker FROM dim_assets 
                    WHERE industry = ? AND ticker != ?
                    LIMIT ?
                """
                peers = con.execute(peers_query, (ind, ticker, limit)).fetchall()
                peer_list = [x[0] for x in peers]
                
                # Filter out SYN tickers in Production
                if Config.DATA_STRATEGY == "PRODUCTION":
                    peer_list = [p for p in peer_list if not p.startswith("SYN")]
                
                # Auto-Expand if empty
                # TRACE: Finding the hang
                if len(peer_list) < 3 and Config.GOOGLE_API_KEY:
                     should_expand = False
                     
                     # Check last update time
                     try:
                         # print(f"DEBUG: Checking dim_competitors for {ticker}...")
                         # TIMEOUT GUARD: If this query hangs, we assume stale.
                         # Although DuckDB shouldn't hang on read.
                         last_update_row = con.execute("SELECT MAX(created_at) FROM dim_competitors WHERE ticker_a=?", (ticker,)).fetchone()
                         # print(f"DEBUG: Check complete. Row: {last_update_row}")
                         if last_update_row and last_update_row[0]:
                             last_ts = last_update_row[0]
                             # DuckDB returns datetime
                             from datetime import datetime, timedelta
                             if (datetime.now() - last_ts).days > 7:
                                 should_expand = True
                             else:
                                 print(f"✨ InsightManager: Peer Knowledge is fresh (Updated {last_ts}). Skipping AI.")
                         else:
                             should_expand = True # Never checked
                     except Exception as e:
                         print(f"Peer Check Warning: {e}")
                         should_expand = True # Default to try if check fails
                     
                     if should_expand:
                         print(f"🧠 Just-in-Time AI Research for {ticker} Peers (Weekly Refresh)...")
                         if self.expand_knowledge(ticker):
                             # Re-fetch industry
                             r2 = con.execute("SELECT industry FROM dim_assets WHERE ticker=?", (ticker,)).fetchone()
                             if r2:
                                 ind = r2[0]
                                 peers = con.execute(peers_query, (ind, ticker, limit)).fetchall()
                                 peer_list = [x[0] for x in peers]

                # Fallback: If still few peers, try same SECTOR (Broader Context)
                if len(peer_list) < 3:
                     sector_query = """
                        SELECT ticker FROM dim_assets 
                        WHERE sector = ? AND ticker != ? AND industry != ?
                        LIMIT ?
                     """
                     needed = limit - len(peer_list)
                     if needed > 0:
                         sec_peers = con.execute(sector_query, (sec, ticker, ind, needed)).fetchall()
                         peer_list.extend([x[0] for x in sec_peers])

                # Fallback 2: Sector Aliases (Handle YFinance vs GICS discrepancies)
                if len(peer_list) < 3:
                     aliases = {
                         "Consumer Cyclical": ["Consumer Discretionary"],
                         "Consumer Discretionary": ["Consumer Cyclical"],
                         "Technology": ["Information Technology"],
                         "Information Technology": ["Technology"],
                         "Healthcare": ["Health Care"],
                         "Health Care": ["Healthcare"],
                         "Financial Services": ["Financials"],
                         "Financials": ["Financial Services", "Finance"],
                         "Finance": ["Financials"]
                     }
                     target_aliases = aliases.get(sec, [])
                     # Only try aliases if we have them and still need peers
                     if target_aliases:
                         needed = limit - len(peer_list)
                         if needed > 0:
                             placeholders = ', '.join(['?'] * len(target_aliases))
                             alias_query = f"""
                                SELECT ticker FROM dim_assets 
                                WHERE sector IN ({placeholders}) AND ticker != ?
                                LIMIT ?
                             """
                             params = target_aliases + [ticker, needed]
                             alias_peers = con.execute(alias_query, params).fetchall()
                             peer_list.extend([x[0] for x in alias_peers])

                return peer_list
            finally:
                con.close()

        info = self.database.get(ticker)
        if not info: return []
        target_industry = info["industry"]
        peers = []
        for t, data in self.database.items():
            if t == ticker: continue
            if data.get("industry") == target_industry:
                peers.append(t)
        return peers[:limit]

    def expand_knowledge(self, ticker: str) -> bool:
        """
        Uses Gemini to research a stock AND its competitors.
        """
        api_key = Config.GOOGLE_API_KEY
        if not api_key: return False
            
        try:
            genai.configure(api_key=api_key)
            # Use gemini-flash-latest (valid free tier in this env)
            model = genai.GenerativeModel('gemini-flash-latest')
            
            prompt = f"""
            Research the stock {ticker}.
            1. Identify its correct GICS Sector and Industry.
            2. Identify its Top 5-10 Direct Competitors (Publicly Traded).
            
            Return STRICTLY valid JSON (no markdown). Structure:
            {{
                "target": {{ 
                    "ticker": "{ticker}",
                    "name": "Company Name",
                    "sector": "Sector Name",
                    "industry": "Industry Name"
                }},
                "competitors": [
                    {{ "ticker": "TICKER", "name": "Comp Name", "sector": "Comp Sector", "industry": "Comp Industry" }},
                    ...
                ]
            }}
            """
            
            # Retry loop for Rate Limits
            import time
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = model.generate_content(prompt)
                    break # Success
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        print(f"Ai Rate Limit (429). Retrying in 4s... ({attempt+1}/{max_retries})")
                        time.sleep(4)
                    else:
                        raise e 
            
            if not response: return False
            # ... (Cleaning logic same as before)
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
                
            data = json.loads(text.strip())
            tgt = data.get("target")
            comps = data.get("competitors", [])
            
            if Config.USE_SYNTHETIC_DB and self.db:
                con = self.db.get_connection()
                try:
                    if tgt:
                         con.execute("""
                            UPDATE dim_assets 
                            SET name=?, sector=?, industry=? 
                            WHERE ticker=?
                         """, (tgt.get("name"), tgt.get("sector"), tgt.get("industry"), ticker))
                         # Also upsert if missing (in case UPDATE affects 0 rows)
                         con.execute("""
                            INSERT OR IGNORE INTO dim_assets (ticker, name, sector, industry)
                            VALUES (?, ?, ?, ?)
                         """, (ticker, tgt.get("name"), tgt.get("sector"), tgt.get("industry")))

                    for c in comps:
                        ct = c.get("ticker")
                        if ct:
                             con.execute("""
                                INSERT OR IGNORE INTO dim_assets (ticker, name, sector, industry)
                                VALUES (?, ?, ?, ?)
                             """, (ct, c.get("name"), c.get("sector"), c.get("industry")))
                             
                             con.execute("""
                                INSERT OR IGNORE INTO dim_competitors (ticker_a, ticker_b, reason)
                                VALUES (?, ?, ?)
                             """, (ticker, ct, "AI Identified"))
                             
                             # Also add reverse relationship for easier lookup
                             con.execute("""
                                INSERT OR IGNORE INTO dim_competitors (ticker_a, ticker_b, reason)
                                VALUES (?, ?, ?)
                             """, (ct, ticker, "AI Identified"))
                             
                    # CRITICAL FIX: Update timestamp for ALL competitors (new and old) to prevent infinite JIT loop
                    con.execute("UPDATE dim_competitors SET created_at = CURRENT_TIMESTAMP WHERE ticker_a = ?", (ticker,))
                    print(f"✅ Peer Knowledge Updated for {ticker}")
                    return True
                except Exception as e:
                    print(f"DB Expand Error: {e}")
                    return False
                finally:
                    con.close()
            
            # --- JSON Fallback ---
            if tgt:
                current = self.database.get(ticker, {})
                current["name"] = tgt.get("name", current.get("name"))
                current["sector"] = tgt.get("sector", current.get("sector"))
                current["industry"] = tgt.get("industry", current.get("industry"))
                comp_tickers = [c["ticker"] for c in comps]
                current["competitors"] = comp_tickers
                self.database[ticker] = current
                
            for c in comps:
                c_ticker = c.get("ticker")
                if c_ticker and c_ticker not in self.database:
                    self.database[c_ticker] = {
                        "name": c.get("name"),
                        "sector": c.get("sector"),
                        "industry": c.get("industry"),
                        "competitors": [] 
                    }
            self._save_database()
            return True
                
        except Exception as e:
            print(f"Gemini Expansion Error: {e}")
            
        return False

    def extract_tickers_from_text(self, text: str) -> List[str]:
        """
        Uses Gemini to extract stock tickers from text (news headlines/summaries).
        """
        api_key = Config.GOOGLE_API_KEY
        if not api_key: return []
            
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-latest')
            
            prompt = f"""
            Identify all publicly traded stock tickers mentioned in the following text.
            Text: "{text}"
            
            Return STRICTLY valid JSON (no markdown) as a list of strings.
            Example: ["AAPL", "GOOGL"]
            If none, return [].
            """
            
            response = model.generate_content(prompt)
            if not response: return []
            
            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"): cleaned_text = cleaned_text[:-3]
            
            tickers = json.loads(cleaned_text.strip())
            if isinstance(tickers, list):
                # Basic validation (uppercase, 1-5 chars)
                return [t.upper() for t in tickers if isinstance(t, str) and 1 <= len(t) <= 5]
            return []
            
        except Exception as e:
            print(f"Gemini Ticker Extraction Error: {e}")
            return []


    def get_recommendations_for_portfolio(self, holdings: List[str]) -> Dict[str, List[Dict]]:
        """
        Aggregates Competitors and Peers for all holdings.
        """
        recs = {
            "competitors": [],
            "peers": []
        }
        
        seen_competitors = set(holdings) 
        seen_peers = set(holdings)
        
        for holding in holdings:
            # Competitors
            comps = self.get_competitors(holding)
            for c in comps:
                if c not in seen_competitors:
                    recs["competitors"].append({
                        "ticker": c,
                        "name": self.database.get(c, {}).get("name", c),
                        "reason": f"Competitor of {holding}"
                    })
                    seen_competitors.add(c)
            
            # Peers
            peers = self.get_industry_peers(holding)
            for p in peers:
                if p not in seen_peers:
                    recs["peers"].append({
                        "ticker": p,
                        "name": self.database.get(p, {}).get("name", p),
                        "reason": f"Industry Peer of {holding}"
                    })
                    seen_peers.add(p)
                    
        return recs
    def get_discovery_candidates(self, core_tickers: List[str], limit: int = 5, depth: int = 3) -> List[str]:
        """
        Finds 'neighbor' tickers (competitors) that are NOT in the core_tickers list.
        Traverses the relationship graph up to `depth` levels.
        """
        if not core_tickers: return []
        
        known_universe = set(core_tickers)
        candidates = set()
        frontier = set(core_tickers)
        
        # Limit total traversal to avoid explosion, but keep high enough to find gems
        traversal_limit = limit * 5 
        
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                for d in range(depth):
                    if not frontier: break
                    
                    # Batch Query for Frontier
                    placeholders = ','.join(['?'] * len(frontier))
                    query = f"""
                        SELECT DISTINCT ticker_b 
                        FROM dim_competitors 
                        WHERE ticker_a IN ({placeholders})
                    """
                    rows = con.execute(query, list(frontier)).fetchall()
                    
                    new_frontier = set()
                    for r in rows:
                        t = r[0]
                        if t and 1 <= len(t) <= 5 and " " not in t:
                            if t not in known_universe:
                                candidates.add(t)
                                new_frontier.add(t)
                                known_universe.add(t) # Mark as seen
                    
                    # Prepare next layer
                    frontier = new_frontier
                    
                    if len(candidates) >= traversal_limit:
                        break
                        
                # After gathering "depth" layers, sample down to requested limit
                if len(candidates) > limit:
                     import random
                     return random.sample(list(candidates), limit)
                return list(candidates)
                
            except Exception as e:
                print(f"Discovery Error: {e}")
            finally:
                con.close()
                
        else:
            # JSON Fallback (Iterative)
            import random
            frontier = set(core_tickers)
            
            for d in range(depth):
                new_frontier = set()
                for t in frontier:
                    comps = self.get_competitors(t)
                    for c in comps:
                        if c not in known_universe:
                            candidates.add(c)
                            new_frontier.add(c)
                            known_universe.add(c)
                frontier = new_frontier
                if not frontier: break
            
            # Sample
            if candidates:
                try:
                    return random.sample(list(candidates), min(len(candidates), limit))
                except: return list(candidates)
                
        return list(candidates)
