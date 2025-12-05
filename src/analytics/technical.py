import pandas as pd
import ta
import numpy as np

def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators to the dataframe.
    
    Args:
        df: DataFrame with columns [open, high, low, close, volume]
        
    Returns:
        DataFrame with added technical features
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Moving Averages
    df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['sma_200'] = ta.trend.sma_indicator(df['close'], window=200)
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # Bollinger Bands
    bollinger = ta.volatility.BollingerBands(df['close'])
    df['bb_high'] = bollinger.bollinger_hband()
    df['bb_low'] = bollinger.bollinger_lband()
    
    # Volatility (ATR)
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
    
    # Returns
    df['log_return'] = pd.Series(df['close']).pct_change().apply(lambda x: np.log(1 + x))
    
    return df
