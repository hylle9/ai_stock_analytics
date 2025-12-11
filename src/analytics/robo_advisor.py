from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd
from src.utils.config import Config

class RoboAdvisor:
    """
    Scans the market (cached DuckDB) for technical signals and opportunities.
    """
    def __init__(self):
        self.db = None
        if Config.USE_SYNTHETIC_DB:
            from src.data.db_manager import DBManager
            self.db = DBManager()
            
    def scan_market(self, portfolio_tickers: List[str] = None) -> Dict[str, List[Dict]]:
        """
        Scans all tickers in DB for:
        1. Portfolio Rising (SMA20 > SMA50)
        2. Portfolio Falling (SMA20 < SMA50)
        3. New Opportunities (Golden Cross in last 10 days, NOT in portfolio)
        """
        if not self.db:
            return {}
            
        con = self.db.get_connection()
        if not portfolio_tickers:
            portfolio_tickers = []
            
        try:
            # 1. Efficient Window Function Query
            # We need 90 days of history to compute SMA50 accurately for the last 10 days
            # PARTITION BY ticker ensures calculations don't bleed between stocks
            query = """
            WITH smas AS (
                SELECT 
                    ticker, 
                    date, 
                    close,
                    AVG(close) OVER (
                        PARTITION BY ticker 
                        ORDER BY date 
                        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                    ) as sma20,
                    AVG(close) OVER (
                        PARTITION BY ticker 
                        ORDER BY date 
                        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
                    ) as sma50,
                    ROW_NUMBER() OVER (
                        PARTITION BY ticker 
                        ORDER BY date DESC
                    ) as rn
                FROM fact_market_data
                WHERE date >= (current_date() - INTERVAL 90 DAY)
            )
            SELECT ticker, date, close, sma20, sma50 
            FROM smas 
            WHERE rn <= 11  -- Get last 10 days + 1 buffer for robust diffs
            ORDER BY ticker, date DESC
            """
            
            df = con.execute(query).fetchdf()
            
            if df.empty:
                return {
                    "rising": [],
                    "falling": [],
                    "new_opps": []
                }
                
            # 2. Process Results
            rising = []
            falling = []
            new_opps = []
            
            # Group by ticker
            grouped = df.groupby('ticker')
            
            for ticker, group in grouped:
                # Group is ordered DESC by date (rn 1 is latest)
                latest = group.iloc[0]
                
                sma20 = latest['sma20']
                sma50 = latest['sma50']
                price = latest['close']
                
                is_portfolio = ticker in portfolio_tickers
                
                # Signal State
                is_golden = sma20 > sma50
                diff_pct = (sma20 - sma50) / sma50 * 100
                
                item = {
                    "ticker": ticker,
                    "price": price,
                    "sma20": sma20,
                    "sma50": sma50,
                    "diff_pct": diff_pct,
                    "date": latest['date']
                }
                
                if is_portfolio:
                    if is_golden:
                        rising.append(item)
                    else:
                        falling.append(item)
                else:
                    # Check for "New" Golden Cross (Last 10 days)
                    # We need to find if it WAS NOT golden recently, and IS golden now.
                    # Iterate through history (up to 10 days)
                    # Use 'sma20' and 'sma50' from columns
                    
                    # If currently golden
                    if is_golden:
                        # Look for a crossover event in the window
                        # A crossover means: on Day X, 20 > 50. On Day X-1, 20 <= 50.
                        
                        crossed_recently = False
                        days_ago = 0
                        
                        # We have 11 rows max. Iterate.
                        # group is DESC.
                        # i=0 is today. i=1 is yesterday.
                        for i in range(len(group) - 1):
                            curr_row = group.iloc[i]
                            prev_row = group.iloc[i+1] # Day before
                            
                            curr_state = curr_row['sma20'] > curr_row['sma50']
                            prev_state = prev_row['sma20'] <= prev_row['sma50']
                            
                            if curr_state and prev_state:
                                crossed_recently = True
                                days_ago = i
                                break
                        
                        if crossed_recently:
                            item["days_ago"] = days_ago
                            new_opps.append(item)
                            
            return {
                "rising": sorted(rising, key=lambda x: x['diff_pct'], reverse=True),
                "falling": sorted(falling, key=lambda x: x['diff_pct']), # Most negative first
                "new_opps": sorted(new_opps, key=lambda x: x['days_ago']) # Most recent first
            }
            
        except Exception as e:
            print(f"Robo Advisor Scan Error: {e}")
            return {}
        finally:
            con.close()
