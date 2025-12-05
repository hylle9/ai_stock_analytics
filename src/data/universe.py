import json
import os
from typing import List, Dict, Optional

class Universe:
    """
    Manages a collection of stock tickers.
    """
    def __init__(self, name: str, tickers: List[str], description: str = ""):
        self.name = name
        self.tickers = sorted(list(set(tickers)))  # Deduplicate and sort
        self.description = description

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "tickers": self.tickers,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Universe':
        return cls(
            name=data["name"],
            tickers=data["tickers"],
            description=data.get("description", "")
        )

class UniverseManager:
    """
    Persists and retrieves Universes.
    """
    def __init__(self, storage_path: str = "data/universes"):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Seed default universe if empty
        if not os.listdir(self.storage_path):
            self.save_universe(Universe(
                name="Big_Tech_10", 
                tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "AMD", "INTC"],
                description="Top 10 US Tech stocks"
            ))

    def save_universe(self, universe: Universe):
        file_path = os.path.join(self.storage_path, f"{universe.name}.json")
        with open(file_path, 'w') as f:
            json.dump(universe.to_dict(), f, indent=4)

    def load_universe(self, name: str) -> Optional[Universe]:
        file_path = os.path.join(self.storage_path, f"{name}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r') as f:
            data = json.load(f)
        return Universe.from_dict(data)

    def list_universes(self) -> List[str]:
        files = [f for f in os.listdir(self.storage_path) if f.endswith(".json")]
        return sorted([f.replace(".json", "") for f in files])
