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

    def __init__(self):
        self.database = {}
        self._load_database()

    def _load_database(self):
        # 1. Try to load persistent expansion (Gemini Data)
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    self.database = json.load(f)
                print(f"Loaded {len(self.database)} items from {self.STORAGE_PATH}")
            except Exception as e:
                print(f"Error loading relationships: {e}")
        else:
            print("No persistence file found. Starting fresh.")
        
        # 2. Always sync with Seed (Golden Master)
        print("Syncing database with S&P 500 seed...")
        self._load_seed()
        self._save_database()

    def _load_seed(self):
        if os.path.exists(self.SEED_PATH):
            try:
                with open(self.SEED_PATH, 'r') as f:
                    seed_data = json.load(f)
                    
                    for k, v in seed_data.items():
                        if k not in self.database:
                            self.database[k] = v
                        else:
                            # Overwrite metadata to ensure GICS standardization
                            self.database[k]["sector"] = v["sector"]
                            self.database[k]["industry"] = v["industry"]
                            # Preserve found competitors. Only use seed if we have none.
                            if "competitors" in v and v["competitors"] and not self.database[k].get("competitors"):
                                self.database[k]["competitors"] = v["competitors"]

            except Exception as e:
                print(f"Error loading seed: {e}")
        else:
             print("Warning: Seed file not found.")
        
    def _save_database(self):
        """Atomic save to prevent corruption"""
        try:
            os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
            temp_path = self.STORAGE_PATH + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.database, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.STORAGE_PATH)
            print(f"Saved {len(self.database)} items to {self.STORAGE_PATH}")
        except Exception as e:
            print(f"CRITICAL ERROR SAVING DATABASE: {e}")
    
    def get_info(self, ticker: str) -> Optional[Dict]:
        return self.database.get(ticker)
        
    def get_competitors(self, ticker: str) -> List[str]:
        info = self.get_info(ticker)
        if info:
            return info.get("competitors", [])
        return []
        
    def get_industry_peers(self, ticker, limit=10) -> List[str]:
        info = self.get_info(ticker)
        if not info:
            return []
            
        target_industry = info["industry"]
        target_sector = info["sector"]
        
        peers = []
        for t, data in self.database.items():
            if t == ticker:
                continue
            
            # Match Industry (Primary)
            if data.get("industry") == target_industry:
                peers.append(t)
            # Match Sector (Secondary fallback if few industry matches)
            # elif data.get("sector") == target_sector:
            #      pass
                 
        return peers[:limit]

    def expand_knowledge(self, ticker: str) -> bool:
        """
        Uses Gemini to research a stock AND its competitors, adding them all to the database.
        Returns True if successful.
        """
        api_key = Config.GOOGLE_API_KEY
        if not api_key:
            return False
            
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"""
            Research the stock {ticker}.
            1. Identify its correct GICS Sector and Industry.
            2. Identify its Top 5 Direct Competitors (Publicly Traded).
            
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
            
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean possible markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            data = json.loads(text.strip())
            
            # Process Target
            tgt = data.get("target")
            comps = data.get("competitors", [])
            
            if tgt:
                # Get existing data to preserve if needed, or simply update
                current = self.database.get(ticker, {})
                
                # Update basic info
                current["name"] = tgt.get("name", current.get("name"))
                current["sector"] = tgt.get("sector", current.get("sector"))
                current["industry"] = tgt.get("industry", current.get("industry"))
                
                # Update competitors list
                comp_tickers = [c["ticker"] for c in comps]
                current["competitors"] = comp_tickers
                
                self.database[ticker] = current
                
            # Process Competitors (Add them to DB if missing!)
            for c in comps:
                c_ticker = c.get("ticker")
                if c_ticker and c_ticker not in self.database:
                    self.database[c_ticker] = {
                        "name": c.get("name"),
                        "sector": c.get("sector"),
                        "industry": c.get("industry"),
                        "competitors": [] # We don't know their competitors yet
                    }
            
            self._save_database()
            return True
                
        except Exception as e:
            print(f"Gemini Expansion Error: {e}")
            
        return False

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
