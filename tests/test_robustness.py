import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analytics.technical import add_technical_features
from src.data.relationships import RelationshipManager
from src.utils.config import Config

class TestRobustness:
    """
    Tests to ensure system stability against edge cases and data pollution.
    Prevents regressions of Critical fixes.
    """

    def test_technical_empty_dataframe(self):
        """Guard: Ensure add_technical_features handles empty DF without crash."""
        df = pd.DataFrame()
        result = add_technical_features(df)
        assert result.empty

    def test_technical_small_dataframe_atr_crash(self):
        """
        Guard: Ensure add_technical_features handles DF < 14 rows (ATR Window).
        Regression Test for IndexError crash.
        """
        # Create tiny dataframe (5 rows < 14)
        data = {
            'open': [100]*5, 'high': [105]*5, 'low': [95]*5, 
            'close': [102]*5, 'volume': [1000]*5
        }
        df = pd.DataFrame(data)
        
        # Should not crash
        try:
            result = add_technical_features(df)
        except IndexError:
            pytest.fail("add_technical_features crashed on small dataframe (IndexError)")
        except Exception as e:
            pytest.fail(f"add_technical_features crashed: {e}")
            
        # Verify ATR is NaN (or handled) but not missing/crashing
        assert 'atr' in result.columns
        assert pd.isna(result['atr'].iloc[-1]) # Should be NaN for small window via try-except fallback

    def test_pollution_filtering_in_production(self):
        """
        Guard: Ensure RelationshipManager filters out 'SYN' tickers in Production Mode.
        Regression Test for Data Pollution.
        """
        # Save original config
        original_strategy = Config.DATA_STRATEGY
        
        try:
            # Force Production
            Config.DATA_STRATEGY = "PRODUCTION"
            
            # Mock DB Connection
            mock_con = MagicMock()
            
            # Setup side_effect for execute().fetchone() and execute().fetchall()
            # The code calls:
            # 1. execute(asset_query).fetchone() -> Need (Industry, Sector)
            # 2. execute(peers_query).fetchall() -> Need [(Ticker,), (Ticker,)...]
            
            # Since mock_con.execute returns a cursor (which is mock_con in fluent API often, 
            # or a new mock), we need to structure it carefully.
            
            mock_cursor = MagicMock()
            mock_con.execute.return_value = mock_cursor
            
            # First call is fetchone (Asset lookup) -> ("Tech", "Software")
            # Second call is fetchall (Peers) -> List of tickers
            # However, typically execute() returns a cursor. 
            
            # Lets define behavior based on the query string if possible, or just sequential returns if side_effect used on cursor methods.
            # Simpler: mock_cursor.fetchone.return_value = ("Software", "Technology")
            # mock_cursor.fetchall.return_value = [("AAPL",), ("SYN001",), ("MSFT",)]
            # But the code creates a NEW cursor for each execute usually? No, "con.execute" returns cursor.
            
            mock_cursor.fetchone.return_value = ("Software", "Technology")
            mock_cursor.fetchall.side_effect = [
                # First fetchall is for peers
                # Need >= 3 REAL tickers to avoid fallback "expand_knowledge"
                [("AAPL",), ("SYN001",), ("MSFT",), ("SYN002",), ("GOOGL",)],
                # Possible subsequent calls (fallback) - empty
                []
            ]
            
            rm = RelationshipManager()
            rm.db = MagicMock()
            rm.db.get_connection.return_value = mock_con
            
            # Mock DuckDB mode to force DB path
            with patch("src.utils.config.Config.USE_SYNTHETIC_DB", True):
                peers = rm.get_industry_peers("AAPL")
                
            # Assertions
            assert "AAPL" in peers
            assert "MSFT" in peers
            assert "SYN001" not in peers
            assert "SYN002" not in peers
            
        finally:
            # Restore
            Config.DATA_STRATEGY = original_strategy
