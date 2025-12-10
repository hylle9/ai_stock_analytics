import pandas as pd
import numpy as np

def calculate_returns(series: pd.Series, period: int = 1) -> pd.Series:
    """
    Calculate percentage returns over a given period.
    """
    return series.pct_change(period)

def calculate_log_returns(series: pd.Series) -> pd.Series:
    """
    Calculate log returns.
    """
    return np.log(series / series.shift(1))

def calculate_volatility(returns: pd.Series, window: int = 20, annualized: bool = True) -> pd.Series:
    """
    Calculate rolling volatility (standard deviation of returns).
    """
    vol = returns.rolling(window=window).std()
    if annualized:
        vol = vol * np.sqrt(252)
    return vol

def calculate_drawdown(series: pd.Series) -> pd.Series:
    """
    Calculate drawdown from rolling peak.
    """
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max
    return drawdown

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculate annualized Sharpe Ratio.
    """
    excess_returns = returns - risk_free_rate/252
    if excess_returns.std() == 0:
        return 0.0
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()

def calculate_relative_volume(df: pd.DataFrame, window: int = 20) -> float:
    """
    Calculate current volume relative to moving average.
    Returns ratio (e.g. 1.5 = 50% above average).
    Returns 0.0 if not enough data.
    """
    if df.empty or 'volume' not in df.columns or len(df) < window:
        return 0.0
        
    avg_vol = df['volume'].rolling(window=window).mean().iloc[-1]
    curr_vol = df['volume'].iloc[-1]
    
    if avg_vol == 0:
        return 0.0
        
    return curr_vol / avg_vol

def calculate_volume_acceleration(df: pd.DataFrame, window: int = 3) -> float:
    """
    Calculate the rate of change of volume over a short window.
    Leading indicator for sudden interest.
    Returns: decimal % change (e.g. 0.5 = 50% increase).
    """
    if df.empty or 'volume' not in df.columns or len(df) < window:
        return 0.0
        
    # We want the trend of the last few days
    # Simple approach: (Vol_now - Vol_window_ago) / Vol_window_ago
    # Better: Average of daily pct changes?
    # Let's use simple ROC of the smoothed volume to avoid noise
    
    vol = df['volume']
    curr = vol.iloc[-1]
    prev = vol.iloc[-window]
    
    if prev == 0:
        return 0.0
        
    return (curr - prev) / prev

def calculate_trend_strength(df: pd.DataFrame) -> float:
    """
    Calculate a normalized trend strength score (-1.0 to 1.0)
    combining RSI and SMA alignment.
    
    Logic:
    - RSI Component (50%): (RSI - 50) / 50
    - SMA Component (50%):
        - Price > SMA200: +0.5
        - Price > SMA50: +0.5
        - Price < SMA200: -0.5
        - Price < SMA50: -0.5
        
    Returns:
        float: -1.0 (Strong Bear) to 1.0 (Strong Bull)
    """
    if df.empty: return 0.0
    
    # 1. RSI Component
    rsi_score = 0.0
    if 'rsi' in df.columns:
        rsi_val = df['rsi'].iloc[-1]
        rsi_score = (rsi_val - 50) / 50.0 # -1 to 1
        
    # 2. SMA Component
    sma_score = 0.0
    price = df['close'].iloc[-1]
    
    # SMA 200 (Structural)
    if 'sma_200' in df.columns:
        sma200 = df['sma_200'].iloc[-1]
        if not pd.isna(sma200):
            if price > sma200: sma_score += 0.5
            else: sma_score -= 0.5
            
    # SMA 50 (Medium Term)
    if 'sma_50' in df.columns:
        sma50 = df['sma_50'].iloc[-1]
        if not pd.isna(sma50):
            if price > sma50: sma_score += 0.5
            else: sma_score -= 0.5
            
    # 3. Combine
    # rsi_score is -1 to 1
    # sma_score is -1 to 1
    # Average them
    total_trend = (rsi_score + sma_score) / 2.0
    
    return max(-1.0, min(1.0, total_trend))
