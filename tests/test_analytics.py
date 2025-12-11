import pytest
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analytics.fusion import FusionEngine
from src.analytics.backtester import run_sma_strategy

class TestAnalytics:
    
    def test_pressure_score_calculation(self):
        """Verify weighted average mechanics of Pressure Score."""
        fusion = FusionEngine()
        
        # Perfect Score Inputs
        score = fusion.calculate_pressure_score(
            price_trend=1.0,        # +30
            volatility_rank=1.0,    # +20
            sentiment_score=1.0,    # +20 (part of Hybrid)
            attention_score=1.0,    # +10
            relative_volume=2.0,    # +10
            volume_acceleration=0.5 # +10
        )
        # Should be near 100 
        # Note: FusionEngine logic clamps and weights. 
        # We expect a high score.
        assert score > 90
        assert score <= 100

    def test_pressure_score_bounds(self):
        """Ensure score is always 0-100."""
        fusion = FusionEngine()
        # Negative/Zero inputs
        score = fusion.calculate_pressure_score(-1, 0, -1, 0, 0, 0)
        assert score >= 0
        assert score <= 100

    def test_sma_strategy_buy_signal(self):
        """
        Verify BUY Signal Logic:
        Close > SMA50 > SMA200 (Golden Cross Setup)
        """
        data = {
            'close': [100, 105, 110],
            'sma_50': [90, 92, 95],
            'sma_20': [88, 93, 100],  # Crosses SMA50 (92->93) at index 1
            'sma_200': [80, 82, 85],
            'rsi': [60, 60, 60]       # Neutral
        }
        df = pd.DataFrame(data)
        
        # Run Strategy
        # Index 0: 20(88) <= 50(90)
        # Index 1: 20(93) > 50(92) -> CROSSOVER BUY
        result = run_sma_strategy(df, trend_filter_sma200=True)
        
        
        assert result['is_active'] is True
        assert result['trade_count'] > 0 # Should have entered

    def test_sma_strategy_sell_signal(self):
        """
        Verify SELL Signal Logic:
        Close < SMA200 (Trend Breakdown)
        """
        data = {
            'close': [100, 90, 80],
            'sma_50': [110, 108, 105],
            'sma_20': [100, 95, 90],  # Always below SMA50
            'sma_200': [120, 120, 120],
            'rsi': [40, 40, 40]
        }
        df = pd.DataFrame(data)
        
        result = run_sma_strategy(df, trend_filter_sma200=True)
        
        assert result['is_active'] is False # Should be Cash
