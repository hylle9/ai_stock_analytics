import pandas as pd
import numpy as np

def add_microstructure_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add microstructure features (approximated) to the dataframe.
    
    Args:
        df: DataFrame with columns [open, high, low, close, volume]
        
    Returns:
        DataFrame with added microstructure features
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Volume Anomalies (Z-score of volume)
    # Using a rolling window to adapt to changing volume regimes
    rolling_vol_mean = df['volume'].rolling(window=20).mean()
    rolling_vol_std = df['volume'].rolling(window=20).std()
    
    df['volume_z_score'] = (df['volume'] - rolling_vol_mean) / rolling_vol_std
    
    # Price Impact (Amihud Illiquidity Proxy: |Return| / Volume)
    # Higher value = less liquid (price moves more per unit of volume)
    # We add a small epsilon to volume to avoid division by zero
    df['amihud_illiquidity'] = df['close'].pct_change().abs() / (df['volume'] * df['close'] + 1e-9)
    
    # Volatility of High-Low range (Parkinson Volatility proxy)
    df['hl_range'] = (df['high'] - df['low']) / df['close']
    
    # Retail Participation Signal (RPS) Proxy
    # Logic: Retail often chases high volatility and high volume.
    # We combine Volume Z-Score and Intraday Volatility.
    # This is a heuristic for Phase 1.
    
    # Normalize inputs for RPS
    vol_z_norm = (df['volume_z_score'] - df['volume_z_score'].rolling(50).mean()) / df['volume_z_score'].rolling(50).std()
    hl_range_norm = (df['hl_range'] - df['hl_range'].rolling(50).mean()) / df['hl_range'].rolling(50).std()
    
    # Fill NaNs created by rolling
    vol_z_norm = vol_z_norm.fillna(0)
    hl_range_norm = hl_range_norm.fillna(0)
    
    # RPS Proxy: Average of abnormal volume and abnormal volatility
    # Scaled to 0-100 (using sigmoid or min-max, here simple min-max clipping for robustness)
    raw_rps = (vol_z_norm + hl_range_norm) / 2
    
    # Sigmoid-like scaling to 0-100
    df['rps_proxy'] = (1 / (1 + np.exp(-raw_rps))) * 100
    
    return df
