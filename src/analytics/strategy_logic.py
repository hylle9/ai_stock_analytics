
import pandas as pd
from src.analytics.technical import add_technical_features
from src.analytics.backtester import run_sma_strategy

def calculate_strategy_signals(df: pd.DataFrame) -> dict:
    """
    Calculates strategy signals (Buy/Sell, Strong Rec) for a given OHLCV DataFrame.
    
    Args:
        df: DataFrame with OHLCV data.
        
    Returns:
        dict: {
            "strategy_rec": "BUY" | "SELL" | "Unknown",
            "strong_rec": "YES" | "NO",
            "current_rsi": float | None
        }
    """
    results = {
        "strategy_rec": "Unknown",
        "strong_rec": "NO",
        "current_rsi": None
    }
    
    if df is None or df.empty:
        return results

    try:
        # 1. Add Technical Features
        tech_df = add_technical_features(df.copy())
        
        # 2. Extract RSI
        if 'rsi' in tech_df.columns and not tech_df['rsi'].empty:
            last_rsi = tech_df['rsi'].iloc[-1]
            if not pd.isna(last_rsi):
                results["current_rsi"] = last_rsi
                
        # 3. Strategy 1: Long Term Safety (SMA Crossover + Trend Filter)
        # matches logic in stock_view.py
        sim_res = run_sma_strategy(tech_df, trend_filter_sma200=True)
        results["strategy_rec"] = "BUY" if sim_res.get("is_active") else "SELL"
        
        # 4. Strategy 2: Strong but Safe (>15% Trend Strength)
        sim_strong = run_sma_strategy(tech_df, trend_filter_sma200=True, min_trend_strength=0.15)
        results["strong_rec"] = "YES" if sim_strong.get("is_active") else "NO"
        
    except Exception as e:
        print(f"Strategy Calculation Error: {e}")
        
    return results
