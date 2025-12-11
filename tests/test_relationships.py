import pytest
from unittest.mock import MagicMock, patch
from src.data.relationships import RelationshipManager

class MockRelationshipManager(RelationshipManager):
    def __init__(self, mock_db=None):
        self.database = {}
        self.db = mock_db

    def get_competitors(self, ticker):
        # Mock Graph:
        # AAPL -> MSFT, GOOG
        # MSFT -> ORCL
        # ORCL -> SAP
        # SAP -> CRM
        graph = {
            "AAPL": ["MSFT", "GOOG"],
            "MSFT": ["ORCL"],
            "ORCL": ["SAP"],
            "SAP": ["CRM"]
        }
        return graph.get(ticker, [])

def test_discovery_depth_1():
    rm = MockRelationshipManager()
    # Depth 1 from AAPL should find MSFT, GOOG
    candidates = rm.get_discovery_candidates(["AAPL"], limit=10, depth=1)
    assert "MSFT" in candidates
    assert "GOOG" in candidates
    assert "ORCL" not in candidates

def test_discovery_depth_2():
    rm = MockRelationshipManager()
    # Depth 2 from AAPL should find MSFT, GOOG (L1) AND ORCL (L2)
    candidates = rm.get_discovery_candidates(["AAPL"], limit=10, depth=2)
    assert "MSFT" in candidates
    assert "ORCL" in candidates
    assert "SAP" not in candidates

def test_discovery_depth_3():
    rm = MockRelationshipManager()
    # Depth 3 from AAPL should find SAP (L3)
    candidates = rm.get_discovery_candidates(["AAPL"], limit=10, depth=3)
    assert "SAP" in candidates
    assert "CRM" not in candidates # CRM is L4

def test_circular_dependency():
    rm = MockRelationshipManager()
    # A -> B -> A
    rm.get_competitors = MagicMock(side_effect=lambda t: ["B"] if t == "A" else ["A"])
    
    candidates = rm.get_discovery_candidates(["A"], limit=10, depth=3)
    assert "B" in candidates
    # Should complete without infinite loop
