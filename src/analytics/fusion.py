import pandas as pd
import numpy as np
from typing import Dict

class FusionEngine:
    """
    The FusionEngine is the 'Brain' of the analytics system.
    Its job is to take disparate signals (Price, Volatility, Sentiment, Attention)
    and combine them into a single, easy-to-understand 'Pressure Score' (0-100).
    
    Think of this like a credit score for a stock's short-term momentum.
    """
    def __init__(self):
        # Configuration: Weights determine how important each signal is.
        # These sum to 1.0 (100%).
        self.weights = {
            "trend": 0.3,       # 30% - Technical trend (RSI, Moving Averages)
            "volatility": 0.2,  # 20% - Market energy (Bollinger Band width)
            "sentiment": 0.25,  # 25% - News sentiment (Good/Bad news)
            "attention": 0.25   # 25% - Retail volume/chatter (Hype)
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
        
        This function normalizes all inputs to a 0-100 scale and then applies
        a weighted average to produce the final score.
        
        Args:
            price_trend: Normalized trend (-1.0 to 1.0).
                         -1.0 = Strong Downtrend, 1.0 = Strong Uptrend.
            volatility_rank: Normalized volatility (0.0 to 1.0).
                             0.0 = Very Calm, 1.0 = Highly Volatile.
            sentiment_score: Normalized sentiment (-1.0 to 1.0).
                             -1.0 = Very Negative News, 1.0 = Very Positive News.
            attention_score: Normalized social attention (0.0 to 1.0).
                             0.0 = No one talking, 1.0 = Viral.
            relative_volume: Ratio of current volume to average volume (e.g. 1.5 = 150%).
            volume_acceleration: Rate of change of volume (e.g. 0.2 = 20% increase).
            
        Returns:
            Score between 0.0 and 100.0. 
            >70: Strong Buying Pressure (Bullish)
            <30: Strong Selling Pressure (Bearish)
        """
        
        # --- STEP 1: SAFETY CLAMPING ---
        # Data from the wild can be messy. We force inputs into expected ranges
        # to prevent math errors or score blowouts.
        trend_c = max(-1.0, min(1.0, price_trend))      # Clamp between -1 and 1
        vol_c = max(0.0, min(1.0, volatility_rank))     # Clamp between 0 and 1
        sent_c = max(-1.0, min(1.0, sentiment_score))   # Clamp between -1 and 1
        att_c = max(0.0, min(1.0, attention_score))     # Clamp between 0 and 1
        
        # --- STEP 2: NORMALIZATION (MAPPING TO 0-100) ---
        # All components must speak the same language (0 to 100) before we mix them.
        
        # Trend Normalization:
        # Input: -1 (Bearish) to +1 (Bullish)
        # Math: Add 1 to make it 0-2 (Positive). Multiply by 50 to scaling it to 0-100.
        # Result: -1 becomes 0, 0 becomes 50, +1 becomes 100.
        s_trend = (trend_c + 1) * 50
        
        # Sentiment Normalization:
        # Same logic as Trend. Maps -1..+1 to 0..100.
        s_sentiment = (sent_c + 1) * 50
        
        # --- STEP 3: HYBRID RETAIL LOGIC ---
        # "Attention" is complex. It can be explicit (Social Posts) or implicit (Volume spikes).
        # We want to catch breakout moves even if social media hasn't reacted yet.
        
        # A. Social Score (Derived from StockTwits/Reddit)
        # Input 0-1 -> Output 0-100
        s_social = att_c * 100
        
        # B. Volume Anomaly Score (Silent Attention)
        # If relative volume is 1.0 (Normal), score is 0.
        # If relative volume is 3.0 (3x Normal), that's huge. We cap it there by multiplying by 50.
        # (3.0 - 1.0) * 50 = 100.
        s_vol_anom = max(0.0, min(100.0, (relative_volume - 1.0) * 50))
        
        # C. Acceleration Score (Leading Indicator)
        # Is volume *growing* fast? 
        # 0.5 acceleration (50% growth) * 200 = 100 score.
        s_accel = max(0.0, min(100.0, volume_acceleration * 200))
        
        # D. Combine into one "Retail/Attention" Score
        # We take the MAXIMUM of Social, Volume Anomaly, or Acceleration.
        # Rationale: If ANY of these are high, the stock is "In Play".
        s_retail_raw = max(s_social, s_vol_anom)
        
        # Bonus: If volume is accelerating fast (>5%), give it priority.
        if volume_acceleration > 0.05:
            s_retail_raw = max(s_retail_raw, s_accel)
            
        # --- STEP 4: CONTEXTUAL DIRECTIONALITY ---
        # CRITICAL LOGIC: "High Volume" isn't always good.
        # High Volume + Price Crash = Panic Selling (Bearish).
        # High Volume + Price Rise = Breakout (Bullish).
        
        # We determine context by looking at the Trend (RSI/price) and Sentiment.
        is_bullish_context = (trend_c > 0) or (sent_c > 0.2)
        
        if is_bullish_context:
            # Bullish: High attention adds to the score (pushes towards 100).
            s_attention = s_retail_raw
        else:
            # Bearish: High attention means intense selling.
            # We want the score to drop towards 0.
            # So, we invert the retail score. 100 becomes 0, 80 becomes 20.
            s_attention = max(0, 100 - s_retail_raw)

        # --- STEP 5: VOLATILITY HANDLING ---
        # Volatility is similar. High Volatility in an uptrend is "Energy" (Good).
        # High Volatility in a downtrend is "Instability" (Bad).
        if trend_c >= 0:
            # Uptrend: Add volatility to the score (Standard)
            s_vol = vol_c * 100
        else:
            # Downtrend: Penalize volatility (Invert)
            s_vol = 100 - (vol_c * 100)

        # --- STEP 6: FINAL WEIGHTED AVERAGE ---
        # Now we have 4 components, all scaled 0-100, and directionally aligned.
        # We simply sum them up based on their configurable importance (weights).
        score = (
            s_trend * self.weights["trend"] +         # 30% Trend
            s_sentiment * self.weights["sentiment"] + # 25% Sentiment
            s_attention * self.weights["attention"] + # 25% Attention (Hybrid)
            s_vol * self.weights["volatility"]        # 20% Volatility
        )
        
        # Final safety clamp to ensure result is strictly 0-100
        return max(0.0, min(100.0, score))

    def detect_anomalies(self, df: pd.DataFrame) -> list:
        """
        Detect rows where signals diverge (e.g. Price Down but Sentiment Up).
        This helps identify "Divergence" setups which are powerful trading signals.
        """
        anomalies = []
        # TODO: Implement divergence detection logic here.
        # Example: if RSI < 30 (Low) but Sentiment > 0.8 (High) -> Potential Reversal.
        return anomalies
