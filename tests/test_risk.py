import pytest
import pandas as pd
import numpy as np
from src.analytics.risk import calculate_var, calculate_cvar, calculate_risk_metrics

def test_calculate_var_basic():
    returns = pd.Series([0.01, -0.01, 0.02, -0.02])
    var = calculate_var(returns, 0.95)
    assert isinstance(var, float)
    assert var < 0 # VaR is usually negative for losses

def test_calculate_var_handles_nan():
    # NaNs should be ignored
    returns = pd.Series([np.nan, 0.01, -0.01, 0.02, -0.02, np.nan])
    var = calculate_var(returns, 0.95)
    assert not np.isnan(var)
    
    # Should be same as without NaNs
    clean_returns = pd.Series([0.01, -0.01, 0.02, -0.02])
    expected_var = calculate_var(clean_returns, 0.95)
    assert var == expected_var

def test_calculate_cvar_handles_nan():
    returns = pd.Series([np.nan, -0.05, -0.02, 0.01, 0.03, np.nan])
    cvar = calculate_cvar(returns, 0.95)
    assert not np.isnan(cvar)
    assert cvar <= calculate_var(returns, 0.95) # CVaR should be worse (lower) or equal to VaR

def test_calculate_risk_metrics_handles_nan_returns():
    # Simulate returns from pct_change which often starts with NaN
    prices = pd.Series([100, 100, 101, 99, 98])
    returns = prices.pct_change()
    
    metrics = calculate_risk_metrics(returns)
    assert not np.isnan(metrics['VaR_95'])
    assert not np.isnan(metrics['VaR_99'])
    assert not np.isnan(metrics['CVaR_95'])
