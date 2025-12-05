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
