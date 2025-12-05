import pandas as pd
import numpy as np
from typing import Dict

def calculate_var(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    Calculate Historical Value at Risk (VaR).
    """
    if returns.empty:
        return 0.0
    return np.percentile(returns, 100 * (1 - confidence_level))

def calculate_cvar(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    Calculate Conditional Value at Risk (CVaR) / Expected Shortfall.
    """
    if returns.empty:
        return 0.0
    var = calculate_var(returns, confidence_level)
    return returns[returns <= var].mean()

def calculate_risk_metrics(returns: pd.Series) -> Dict[str, float]:
    """
    Calculate a suite of risk metrics.
    """
    return {
        "VaR_95": calculate_var(returns, 0.95),
        "VaR_99": calculate_var(returns, 0.99),
        "CVaR_95": calculate_cvar(returns, 0.95),
        "Volatility_Ann": returns.std() * np.sqrt(252)
    }
