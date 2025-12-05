import pandas as pd
import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Optional

class Portfolio:
    """
    Tracks portfolio holdings and value.
    """
    def __init__(self, initial_cash: float = 100000.0):
        self.cash = initial_cash
        self.holdings: Dict[str, int] = {} # Ticker -> Quantity
        self.history: List[Dict] = []

    def update_holdings(self, ticker: str, quantity: int, price: float):
        """
        Buy (positive quantity) or Sell (negative quantity).
        """
        cost = quantity * price
        if self.cash - cost < 0:
            raise ValueError("Insufficient cash")
        
        self.cash -= cost
        self.holdings[ticker] = self.holdings.get(ticker, 0) + quantity
        
        # Remove if 0
        if self.holdings[ticker] == 0:
            del self.holdings[ticker]

    def get_value(self, current_prices: Dict[str, float]) -> float:
        stock_value = sum(self.holdings.get(t, 0) * p for t, p in current_prices.items())
        return self.cash + stock_value

    def get_allocation(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        total_value = self.get_value(current_prices)
        if total_value == 0:
            return {}
        
        allocation = {t: (q * current_prices.get(t, 0)) / total_value 
                      for t, q in self.holdings.items()}
        allocation['CASH'] = self.cash / total_value
        return allocation

class Optimizer:
    """
    Mean-Variance Optimizer.
    """
    def optimize_mean_variance(self, 
                             expected_returns: pd.Series, 
                             covariance_matrix: pd.DataFrame, 
                             risk_aversion: float = 1.0) -> Dict[str, float]:
        """
        Find optimal weights to maximize: Returns - Risk_Aversion * Variance
        Subject to: sum(weights) = 1, 0 <= weight <= 1
        """
        tickers = expected_returns.index.tolist()
        num_assets = len(tickers)
        
        # Objective function (minimize negative utility)
        def objective(weights):
            port_return = np.sum(returns_arr * weights)
            port_var = np.dot(weights.T, np.dot(cov_arr, weights))
            utility = port_return - 0.5 * risk_aversion * port_var
            return -utility

        returns_arr = expected_returns.values
        cov_arr = covariance_matrix.values
        
        # Constraints
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(num_assets))
        
        initial_weights = num_assets * [1. / num_assets,]
        
        result = minimize(objective, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        
        return dict(zip(tickers, result.x))
