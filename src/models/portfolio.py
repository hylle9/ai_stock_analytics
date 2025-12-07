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

from src.utils.config import Config
if Config.USE_SYNTHETIC_DB:
    pass

class PortfolioManager:
    """
    Manages multiple portfolios with persistence.
    """
    STORAGE_PATH = "data/portfolios.json"

    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
        
        if Config.USE_SYNTHETIC_DB:
            from src.data.db_manager import DBManager
            self.db = DBManager()
            self.load_portfolios_from_db()
        else:
            self.db = None
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

    def load_portfolios_from_db(self):
         con = self.db.get_connection()
         try:
             # Load Portfolios
             p_rows = con.execute("SELECT portfolio_id, name, status, cash FROM dim_portfolios").fetchall()
             for r in p_rows:
                 pid, name, status_str, cash = r
                 try:
                     status = PortfolioStatus(status_str)
                 except: 
                     status = PortfolioStatus.PAUSED
                 
                 p = Portfolio(name, cash, status, pid)
                 
                 # Load Holdings
                 h_rows = con.execute("SELECT ticker, quantity FROM fact_holdings WHERE portfolio_id=?", (pid,)).fetchall()
                 for hr in h_rows:
                     p.holdings[hr[0]] = int(hr[1])
                     
                 self.portfolios[pid] = p
         except Exception as e:
             print(f"DB Load Portfolios Error: {e}")
         finally:
             con.close()

    def save_portfolios(self):
        os.makedirs(os.path.dirname(self.STORAGE_PATH), exist_ok=True)
        data = [p.to_dict() for p in self.portfolios.values()]
        with open(self.STORAGE_PATH, 'w') as f:
            json.dump(data, f, indent=4)

    def create_portfolio(self, name: str, initial_cash: float = 100000.0) -> Portfolio:
        p = Portfolio(name, initial_cash)
        self.portfolios[p.id] = p
        if Config.USE_SYNTHETIC_DB:
            self.save_portfolio(p)
        else:
            self.save_portfolios()
        return p
        
    def delete_portfolio(self, portfolio_id: str):
        if portfolio_id in self.portfolios:
            del self.portfolios[portfolio_id]
            if Config.USE_SYNTHETIC_DB and self.db:
                con = self.db.get_connection()
                try:
                    con.execute("DELETE FROM fact_holdings WHERE portfolio_id=?", (portfolio_id,))
                    con.execute("DELETE FROM dim_portfolios WHERE portfolio_id=?", (portfolio_id,))
                finally:
                    con.close()
            else:
                self.save_portfolios()
            
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        return self.portfolios.get(portfolio_id)
        
    def save_portfolio(self, portfolio: Portfolio):
        """Explicit save trigger for updates"""
        self.portfolios[portfolio.id] = portfolio
        
        if Config.USE_SYNTHETIC_DB and self.db:
            con = self.db.get_connection()
            try:
                # Upsert Portfolio (Delete then Insert to update mutable fields)
                con.execute("DELETE FROM dim_portfolios WHERE portfolio_id=?", (portfolio.id,))
                con.execute("""
                    INSERT INTO dim_portfolios (portfolio_id, name, status, cash)
                    VALUES (?, ?, ?, ?)
                """, (portfolio.id, portfolio.name, portfolio.status.value, portfolio.cash))
                
                # Sync Holdings (Delete all and re-insert)
                con.execute("DELETE FROM fact_holdings WHERE portfolio_id=?", (portfolio.id,))
                
                for t, q in portfolio.holdings.items():
                    # Ensure Asset Exists
                    con.execute("INSERT OR IGNORE INTO dim_assets (ticker) VALUES (?)", (t,))
                    con.execute("""
                        INSERT INTO fact_holdings (portfolio_id, ticker, quantity, avg_buy_price)
                        VALUES (?, ?, ?, 0)
                    """, (portfolio.id, t, float(q)))
            except Exception as e:
                print(f"DB Save Portfolio Error: {e}")
            finally:
                con.close()
            return
            
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
