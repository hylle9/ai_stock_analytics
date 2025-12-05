import pytest
import os
import pandas as pd
from unittest.mock import MagicMock, patch
from src.data.ingestion import DataFetcher

def test_get_cache_path_includes_period():
    fetcher = DataFetcher(cache_dir="dummy/dir")
    period = "3mo"
    ticker = "AAPL"
    
    path = fetcher._get_cache_path(ticker, period)
    assert "AAPL_3mo.parquet" in path
    assert "dummy/dir" in path

@patch("src.data.ingestion.os.path.exists")
@patch("src.data.ingestion.pd.read_parquet")
def test_fetch_ohlcv_uses_cache(mock_read_parquet, mock_exists):
    # Setup
    fetcher = DataFetcher()
    mock_exists.return_value = True
    
    # Mock file modification time to be today
    with patch("src.data.ingestion.os.path.getmtime") as mock_mtime:
        from datetime import datetime
        mock_mtime.return_value = datetime.now().timestamp()
        
        # Test
        fetcher.fetch_ohlcv("AAPL", period="1y")
        
        # Verify
        mock_read_parquet.assert_called_once()
        args, _ = mock_read_parquet.call_args
        assert "AAPL_1y.parquet" in args[0]

def test_fetch_ohlcv_delegates_to_provider_on_cache_miss():
    with patch("src.data.ingestion.os.path.exists", return_value=False):
        fetcher = DataFetcher()
        # Mock the internal provider
        mock_provider = MagicMock()
        mock_df = pd.DataFrame({"close": [100, 101], "volume": [1000, 2000]})
        mock_provider.fetch_ohlcv.return_value = mock_df
        fetcher.provider = mock_provider
        
        # Action
        result = fetcher.fetch_ohlcv("GOOGL", period="5d")
        
        # Verify provider called
        mock_provider.fetch_ohlcv.assert_called_once_with("GOOGL", "5d")
        assert not result.empty

def test_data_fetcher_initialization_fallback():
    # Test that it falls back to YFinanceProvider when no API key
    with patch("src.data.ingestion.Config") as mock_config:
        mock_config.ALPHA_VANTAGE_API_KEY = None
        fetcher = DataFetcher(cache_dir="dummy")
        
        from src.data.providers import YFinanceProvider
        assert isinstance(fetcher.provider, YFinanceProvider)

def test_data_fetcher_initialization_with_key():
    # Test that it uses AlphaVantageProvider when key is present
    with patch("src.data.ingestion.Config") as mock_config:
        mock_config.ALPHA_VANTAGE_API_KEY = "dummy_key"
        fetcher = DataFetcher(cache_dir="dummy")
        
        from src.data.providers import AlphaVantageProvider
        assert isinstance(fetcher.provider, AlphaVantageProvider)

def test_retrieval_success_structure():
    # Verify that the fetched dataframe has the correct columns and structure
    with patch("src.data.ingestion.os.path.exists", return_value=False):
        fetcher = DataFetcher()
        mock_provider = MagicMock()
        
        # specific mock data
        dates = pd.date_range(start="2023-01-01", periods=2)
        mock_df = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [99.0, 100.0],
            "close": [102.0, 104.0],
            "volume": [1000.0, 1500.0]
        }, index=dates)
        
        mock_provider.fetch_ohlcv.return_value = mock_df
        fetcher.provider = mock_provider
        
        df = fetcher.fetch_ohlcv("TEST", "1d")
        
        assert not df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2
        assert df.index.name is None or df.index.name == "" # Index name might vary but structure matters
