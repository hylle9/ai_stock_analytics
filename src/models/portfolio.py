import pandas as pd
import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Optional

from enum import Enum
import uuid

class PortfolioStatus(Enum):
    PAUSED = "Paused"
    LIVE = "Live"
    ARCHIVED = "Archived"

import json
import os

class Portfolio:
    """
    Tracks portfolio holdings, value, and metadata.
    """
    def __init__(self, name: str, initial_cash: float = 100000.0, status: PortfolioStatus = PortfolioStatus.PAUSED, pid: str = None):
        self.id = pid if pid else str(uuid.uuid4())
        self.name = name
        self.status = status
        self.cash = initial_cash
        self.holdings: Dict[str, int] = {} # Ticker -> Quantity
        self.history: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "cash": self.cash,
            "holdings": self.holdings,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Portfolio':
        p = cls(
            name=data["name"],
            initial_cash=data["cash"],
            status=PortfolioStatus(data["status"]),
            pid=data["id"]
        )
        p.holdings = data.get("holdings", {})
        p.history = data.get("history", [])
        return p

    def update_holdings(self, ticker: str, quantity: int, price: float):
        """
        Buy (positive quantity) or Sell (negative quantity).
        """
        cost = quantity * price
        
        # Check cash only on buy
        if quantity > 0 and self.cash - cost < 0:
            raise ValueError("Insufficient cash")
        
        self.cash -= cost
        self.holdings[ticker] = self.holdings.get(ticker, 0) + quantity
        
        # Remove if 0
        if self.holdings[ticker] <= 0:
            if self.holdings[ticker] == 0:
                del self.holdings[ticker]
            elif self.holdings[ticker] < 0:
                # Assuming long-only for now
                self.holdings[ticker] = 0
                del self.holdings[ticker]

    def remove_ticker(self, ticker: str, price: float):
        """
        Sell all shares of ticker.
        """
        qty = self.holdings.get(ticker, 0)
        if qty > 0:
            self.update_holdings(ticker, -qty, price)

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

class PortfolioManager:
    """
    Manages multiple portfolios with persistence.
    """
    STORAGE_PATH = "data/portfolios.json"

    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
        self.load_portfolios()
        
    def load_portfolios(self):
        if os.path.exists(self.STORAGE_PATH):
            try:
                with open(self.STORAGE_PATH, 'r') as f:
                    data = json.load(f)
                    for p_data in data:
                        p = Portfolio.from_dict(p_data)
                        self.portfolios[p.id] = p
            except Exception as e:
                print(f"Error loading portfolios: {e}")

    def save_portfolios(self):
        os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
        data = [p.to_dict() for p in self.portfolios.values()]
        with open(self.STORAGE_PATH, 'w') as f:
            json.dump(data, f, indent=4)

    def create_portfolio(self, name: str, initial_cash: float = 100000.0) -> Portfolio:
        p = Portfolio(name, initial_cash)
        self.portfolios[p.id] = p
        self.save_portfolios()
        return p
        
    def delete_portfolio(self, portfolio_id: str):
        if portfolio_id in self.portfolios:
            del self.portfolios[portfolio_id]
            self.save_portfolios()
            
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        return self.portfolios.get(portfolio_id)
        
    def save_portfolio(self, portfolio: Portfolio):
        """Explicit save trigger for updates"""
        self.portfolios[portfolio.id] = portfolio
        self.save_portfolios()
        
    def list_portfolios(self) -> List[Portfolio]:
        return list(self.portfolios.values())

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
