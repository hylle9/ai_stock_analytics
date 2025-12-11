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

    def test_sma_strong_trend_filter(self):
        """
        Test 'Strong' filter where SMA50 must be > SMA200 by a margin (e.g. 15%).
        """
        # Case A: SMA50 > SMA200 but WEAK (<10%)
        # SMA50=105, SMA200=100 -> 5% diff.
        data_weak = {
            'close': [110, 110, 110],
            'sma_50': [105, 105, 105],
            'sma_20': [108, 108, 108], # > 50, so normally BUY
            'sma_200': [100, 100, 100],
            'rsi': [60, 60, 60]
        }
        df_weak = pd.DataFrame(data_weak)
        
        # Should be filtered out because 5% < 15%
        res_weak = run_sma_strategy(df_weak, trend_filter_sma200=True, min_trend_strength=0.15)
        assert res_weak['is_active'] is False
        
        # Case B: SMA50 > SMA200 STRONG (>15%)
        # SMA50=120, SMA200=100 -> 20% diff.
        # MUST BE RISING to trigger Delayed Entry if not a fresh crossover
        # Or we can simulate a fresh crossover.
        # Let's simulate delayed entry: SMA20 > SMA50 already, AND Rising
        data_strong = {
            'close': [128, 129, 130],
            'sma_50': [118, 119, 120],  # Rising
            'sma_20': [123, 124, 125],  # Rising and > SMA50
            'sma_200': [98, 99, 100],   # Rising
            'rsi': [60, 60, 60]
        }
        df_strong = pd.DataFrame(data_strong)
        
        res_strong = run_sma_strategy(df_strong, trend_filter_sma200=True, min_trend_strength=0.15)
        assert res_strong['is_active'] is True

    def test_backtest_accumulated_return(self):
        """
        Verify that the strategy returns a 'total_return' figure.
        """
        # Simple profitable trade: Buy at 100, Hold, Price goes to 110
        data = {
            'close': [100, 100, 110],
            'sma_50': [90, 90, 90],
            'sma_20': [85, 95, 95], # Crosses 90: Index 0 (85) < 90, Index 1 (95) > 90
            'sma_200': [80, 80, 80],
            'rsi': [50, 50, 50]
        }
        df = pd.DataFrame(data)
        
        res = run_sma_strategy(df, trend_filter_sma200=False)
        
        # Check returns exist
        assert 'total_return' in res
        # Return should be positive (approx 10%)
        # Note: Backtester accumulates realized + unrealized
        assert res['total_return'] > 0.05
