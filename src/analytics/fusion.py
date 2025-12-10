import pandas as pd
import numpy as np
from typing import Dict

class FusionEngine:
    """
    Combines multi-modal signals into a unified 'Pressure Score'.
    """
    def __init__(self):
        # Weights for the pressure score
        self.weights = {
            "trend": 0.3,
            "volatility": 0.2,
            "sentiment": 0.25,
            "attention": 0.25
        }

    def calculate_pressure_score(self, 
                               price_trend: float, 
                               volatility_rank: float, 
                               sentiment_score: float, 
                               attention_score: float,
                               relative_volume: float = 1.0,
                               volume_acceleration: float = 0.0) -> float:
        """
        Calculate a 0-100 score indicating 'pressure' (upward/downward intensity).
        Now includes Hybrid Retail Logic (Social + Volume Anomaly).
        
        Args:
            price_trend: Normalized trend (-1 to 1) e.g. from RSI or ROC
            volatility_rank: Normalized volatility (0 to 1)
            sentiment_score: Normalized sentiment (-1 to 1)
            attention_score: Normalized attention (0 to 1) - SOCIAL ONLY
            relative_volume: Ratio of current vol / avg vol (e.g. 1.5)
            volume_acceleration: Rate of change (e.g. 0.2 = 20% increase)
            
        Returns:
            Score between 0 and 100. 
            50 is neutral. >50 is bullish pressure, <50 is bearish pressure.
        """
        # 1. Clamp Inputs to Expected Ranges
        trend_c = max(-1.0, min(1.0, price_trend))
        vol_c = max(0.0, min(1.0, volatility_rank))
        sent_c = max(-1.0, min(1.0, sentiment_score))
        att_c = max(0.0, min(1.0, attention_score))
        
        # 2. Map Components to 0-100 Scale (Centered at 50)
        
        # Trend: -1 (0) -> 0 (50) -> 1 (100)
        s_trend = (trend_c + 1) * 50
        
        # Sentiment: -1 (0) -> 0 (50) -> 1 (100)
        s_sentiment = (sent_c + 1) * 50
        
        # --- Hybird Retail Score ---
        # We combine Social Attention with Volume Anomalies
        
        # A. Social Score (0-100)
        s_social = att_c * 100
        
        # B. Volume Anomaly Score (Proxy for silent attention)
        # Rel Vol > 1.0 is interesting. Cap at 3.0 (3x volume).
        # Map 1.0 -> 0, 3.0 -> 100
        s_vol_anom = max(0.0, min(100.0, (relative_volume - 1.0) * 50))
        
        # C. Acceleration Score (Leading Indicator 🚀)
        # Accel > 0 is growing. Cap at 0.5 (50% growth/day).
        # Map 0.0 -> 0, 0.5 -> 100
        s_accel = max(0.0, min(100.0, volume_acceleration * 200))
        
        # Hybrid Attention Score
        # If social is defined (>0), it's the gold standard.
        # But if volume is going nuts, we want to respect that too.
        # We assume "Retail Interest" is the MAX of observed social or observed volume action.
        s_retail_raw = max(s_social, s_vol_anom)
        
        # Boost for Acceleration (Leading Edge)
        if volume_acceleration > 0.05:
            s_retail_raw = max(s_retail_raw, s_accel)
            
        # Directionality of Retail Pressure!
        # CRITICAL FIX: High Volume != High Score if Price is crashing.
        # Uses Trend Direction AND Sentiment to determine if Volume is Bullish or Bearish.
        
        # Determine Dominant Direction
        # If Trend is positive (RSI > 50) and Sentiment is not terrible -> Bullish
        # If Trend is negative (RSI < 50) -> Bearish Volume (Panic Selling)
        
        is_bullish_context = (trend_c > 0) or (sent_c > 0.2)
        
        if is_bullish_context:
            s_attention = s_retail_raw
        else:
            # Bearish Context: High volume means high selling pressure.
            # INVERT the score contribution.
            # Instead of adding 0-100, we want it to be 0 (max pressure downwards)
            # But wait, 0 is bearish pressure. So s_attention = 100 - s_retail_raw is correct?
            # If s_retail_raw is 80 (High Vol), s_attention becomes 20 (Strong Bearish Signal).
            s_attention = max(0, 100 - s_retail_raw)

        # Volatility Component
        # High volatility in downtrend = Bearish (0)
        # High volatility in uptrend = Bullish (100) or High Risk?
        # Usually Pressure Score implies "Upside Potential", so Volatility in Uptrend pushes score up.
        if trend_c >= 0:
            s_vol = vol_c * 100
        else:
            s_vol = 100 - (vol_c * 100)

        # 3. Weighted Sum
        score = (
            s_trend * self.weights["trend"] +         # 0.3
            s_sentiment * self.weights["sentiment"] + # 0.25
            s_attention * self.weights["attention"] + # 0.25
            s_vol * self.weights["volatility"]        # 0.2
        )
        
        return max(0.0, min(100.0, score))

    def detect_anomalies(self, df: pd.DataFrame) -> list:
        """
        Detect rows where signals diverge (e.g. Price Down but Sentiment Up).
        """
        anomalies = []
        # Placeholder logic
        return anomalies
