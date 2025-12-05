import pandas as pd
from src.models.portfolio import Portfolio, Optimizer
from src.data.universe import Universe

class Recommender:
    """
    Generates rebalancing recommendations.
    """
    def __init__(self, optimizer: Optimizer):
        self.optimizer = optimizer

    def generate_recommendations(self, 
                               portfolio: Portfolio, 
                               universe: Universe, 
                               current_prices: dict,
                               expected_returns: pd.Series,
                               covariance_matrix: pd.DataFrame,
                               risk_aversion: float = 2.0) -> pd.DataFrame:
        """
        Compare current allocation vs optimal allocation and suggest trades.
        """
        # 1. Calculate Optimal Weights
        optimal_weights = self.optimizer.optimize_mean_variance(
            expected_returns, covariance_matrix, risk_aversion
        )
        
        # 2. Calculate Current Weights
        total_value = portfolio.get_value(current_prices)
        current_weights = portfolio.get_allocation(current_prices)
        
        # 3. Generate Trades
        recommendations = []
        
        for ticker in universe.tickers:
            target_w = optimal_weights.get(ticker, 0.0)
            current_w = current_weights.get(ticker, 0.0)
            
            diff = target_w - current_w
            
            # Threshold to avoid tiny trades
            if abs(diff) > 0.01:
                target_value = target_w * total_value
                current_value = current_w * total_value
                trade_value = target_value - current_value
                price = current_prices.get(ticker, 0)
                
                if price > 0:
                    shares = int(trade_value / price)
                    if shares != 0:
                        recommendations.append({
                            "Ticker": ticker,
                            "Action": "BUY" if shares > 0 else "SELL",
                            "Shares": abs(shares),
                            "Price": price,
                            "Value": abs(shares * price),
                            "Reason": f"Target alloc: {target_w:.1%} (Curr: {current_w:.1%})"
                        })
                        
        return pd.DataFrame(recommendations)
