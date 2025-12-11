import pandas as pd
from typing import Dict, List, Any

def run_sma_strategy(df: pd.DataFrame, 
                     bench_df: pd.DataFrame = None, 
                     investment_size: float = 100000.0, 
                     trend_filter_sma200: bool = False, 
                     min_trend_strength: float = 0.0, 
                     fixed_share_size: int = 0) -> Dict[str, Any]:
    """
    Simulates a Buy-and-Sell strategy based on SMA Crossovers (Backtesting).
    
    This function "plays back" history day-by-day to see how a specific trading rule would have performed.
    
    Strategies Explained:
    1. Standard Golden Cross: Buy when SMA 20 crosses ABOVE SMA 50. Sell when it crosses BELOW.
    2. Trend Filter (Safety): Only buy if price is also above the Long Term Trend (SMA 200).
    3. Min Strength (Momentum): only buy if the crossover is "Strong" (gap between SMA50 and SMA200 is wide).
    
    Args:
        df: The stock data (OHLCV) containing 'close', 'sma_20', 'sma_50', 'sma_200'.
        bench_df: Benchmark data (e.g. S&P500) to compare performance against.
        investment_size: How much cash to invest per trade (e.g. $100,000).
        trend_filter_sma200: If True, blocks trades when price is in a long-term downtrend (Below SMA200).
        min_trend_strength: If >0, requires SMA50 to be X% higher than SMA200 (e.g. 0.15 = 15%).
        fixed_share_size: If >0, simulates buying a specific NUMBER of shares (e.g. 10 shares) instead of a fixed dollar amount.
                          Useful for simulating your actual portfolio.
    
    Returns:
        Dictionary containing:
        - total_pnl: Total Profit/Loss in dollars.
        - trade_count: Number of trades executed.
        - is_active: True if we are currently holding the stock.
        - trades: List of individual trade details.
        - bh_stock_pnl: Profit if we just bought and held the stock (Benchmark 1).
        - bh_bench_pnl: Profit if we bought S&P500 instead (Benchmark 2).
    """
    
    # --- STEP 1: INITIALIZATION ---
    results = {
        "total_pnl": 0.0,
        "trade_count": 0,
        "roi": 0.0,
        "trades": [],
        "is_active": False,
        "status_message": "No trades executed.",
        "bh_stock_pnl": 0.0,
        "bh_bench_pnl": 0.0,
        "bh_bench_roi": 0.0,
        "fixed_shares": fixed_share_size,
        "total_return": 0.0
    }
    
    # Validation: We need at least SMA 20 and 50 to run a Crossover strategy.
    if df.empty or 'sma_20' not in df.columns or 'sma_50' not in df.columns:
        return results
        
    # Validation: If Trend Filter is requested, we MUST have SMA 200 data.
    if trend_filter_sma200 and 'sma_200' not in df.columns:
        return results

    # Ensure chronological order (Oldest first) so we iterate correctly across time.
    df = df.sort_index(ascending=True)
    
    trades = []
    
    # Extract columns to numpy arrays for faster iteration (looping 1000s of rows).
    dates = df.index
    closes = df['close'].values
    sma20s = df['sma_20'].values
    sma50s = df['sma_50'].values
    sma200s = df['sma_200'].values if 'sma_200' in df.columns else None
    
    # State Variable: Tracks if we are currently "IN" a trade.
    current_holding = None # Will store dict: {'buy_price', 'date', ...}
    
    temp_trades_log = [] 
    
    # --- STEP 2: SIMULATION LOOP ---
    # We loop through every day in the dataset, starting from index 1 (because we need "previous day" data to check for crosses).
    for i in range(1, len(df)):
        # Get Previous Day's Values
        prev_20 = sma20s[i-1]
        prev_50 = sma50s[i-1]
        
        # Get Current Day's Values
        curr_20 = sma20s[i]
        curr_50 = sma50s[i]
        
        # Skip if any data is missing (NaN)
        if pd.isna(prev_20) or pd.isna(prev_50) or pd.isna(curr_20) or pd.isna(curr_50):
            continue
            
        date = dates[i]
        price = closes[i]
        
        # --- A. BUY SIGNAL LOGIC ---
        buy_signal = False
        buy_reason = "Standard"
        
        # Logic 1: Standard Golden Cross
        # Did SMA 20 cross FROM below TO above SMA 50?
        if prev_20 <= prev_50 and curr_20 > curr_50:
            buy_signal = True
        
        # Logic 2: Delayed Entry (Smart Re-Entry)
        # Often, a stock is already in an uptrend (20 > 50) but we missed the initial cross.
        # If we are using the "Safety Filter" (trend_filter_sma200), we act smarter.
        # If the trend is UP, and all averages are RISING, we can enter late.
        elif trend_filter_sma200 and (curr_20 > curr_50) and current_holding is None:
             if sma200s is not None:
                 prev_200 = sma200s[i-1]
                 curr_200 = sma200s[i]
                 if not pd.isna(prev_200) and not pd.isna(curr_200):
                     # Rule: Everything must be pointing UP to justify a late entry.
                     sma200_rising = curr_200 > prev_200
                     sma20_rising = curr_20 > prev_20
                     sma50_rising = curr_50 > prev_50
                     
                     if sma200_rising and sma20_rising and sma50_rising:
                         buy_signal = True
                         buy_reason = "Delayed Entry"

        if buy_signal:
            # --- B. FILTERS (Reasons to ignore a buy signal) ---
            is_valid_buy = True
            
            # Filter 1: Long Term Trend (SMA 200)
            # If enabled, we only buy if the long term trend is also positive (Rising).
            if trend_filter_sma200:
                if sma200s is not None:
                     prev_200 = sma200s[i-1]
                     curr_200 = sma200s[i]
                     if not pd.isna(prev_200) and not pd.isna(curr_200):
                         if curr_200 <= prev_200:
                             is_valid_buy = False # REJECT: Long term trend is down/flat.
                     else:
                         is_valid_buy = False # Safety fallback
                else:
                    is_valid_buy = False

            # Filter 2: Trend Strength (Alpha)
            # We want the gap between Medium Term (SMA 50) and Long Term (SMA 200) to be WIDE.
            # A wide gap means the trend has momentum. A narrow gap means it's weak/choppy.
            if is_valid_buy and min_trend_strength > 0:
                if sma200s is not None:
                     curr_200 = sma200s[i]
                     if not pd.isna(curr_200) and curr_200 > 0:
                         # Formula: (SMA50 - SMA200) / SMA200
                         strength = (curr_50 - curr_200) / curr_200
                         if strength <= min_trend_strength:
                             is_valid_buy = False # REJECT: Trend is too weak.
                     else:
                         is_valid_buy = False
                else:
                    is_valid_buy = False

            # --- C. EXECUTE BUY ---
            if is_valid_buy and current_holding is None:
                # Determine Position Size
                if fixed_share_size > 0:
                    # Portfolio Mode: Buy exact number of shares
                    shares_to_buy = float(fixed_share_size)
                    capital_needed = shares_to_buy * float(price)
                else:
                    # Capital Mode: Buy as many shares as $100k allows
                    shares_to_buy = investment_size / float(price)
                    capital_needed = investment_size
                
                # Record the Trade
                current_holding = {
                    "type": "BUY",
                    "date": date,
                    "price": float(price),
                    "shares": shares_to_buy,
                    "invested_capital": capital_needed,
                    "reason": buy_reason
                }
                
                temp_trades_log.append(current_holding)
        
        # --- D. SELL LOGIC (Death Cross) ---
        # Did SMA 20 cross FROM above TO below SMA 50?
        elif prev_20 >= prev_50 and curr_20 < curr_50:
            if current_holding is not None:
                buy_record = current_holding
                
                # Execute Sell
                shares_sold = buy_record['shares']
                sell_value = shares_sold * float(price)
                
                # Calculate Profit/Loss
                pnl = sell_value - buy_record['invested_capital']
                
                sell_record = {
                    "type": "SELL",
                    "date": date,
                    "price": float(price),
                    "shares": shares_sold,
                    "value": sell_value,
                    "reason": "Death Cross"
                }
                
                trade_entry = {
                    "buy_date": buy_record['date'],
                    "buy_price": buy_record['price'],
                    "sell_date": sell_record['date'],
                    "sell_price": sell_record['price'],
                    "shares": shares_sold,
                    "pnl": pnl,
                    "status": "CLOSED",
                    "reason": buy_record.get('reason', 'Standard')
                }
                
                temp_trades_log.append(sell_record)
                trades.append(trade_entry)
                
                # Reset State (We are now in Cash)
                current_holding = None
        
        # (End of Daily Loop)

    # --- STEP 3: CLOSE OPEN POSITIONS ---
    # If the strategy is still holding a stock at the end of the data, we "mark to market".
    # We calculate the value as if we sold it today, just to get a final PnL number.
    if current_holding is not None:
         last_date = df.index[-1]
         last_price = df['close'].iloc[-1]
         
         buy_record = current_holding
         shares_sold = buy_record['shares']
         sell_value = shares_sold * float(last_price)
         
         pnl = sell_value - buy_record['invested_capital']
         
         trade_entry = {
            "buy_date": buy_record['date'],
            "buy_price": buy_record['price'],
            "sell_date": last_date,
            "sell_price": float(last_price),
            "shares": shares_sold,
            "pnl": pnl,
            "status": "OPEN" # Mark as 'OPEN' (Unrealized PnL)
         }
         trades.append(trade_entry)
    
    if not trades:
        return results
        
    # --- STEP 4: AGGREGATE RESULTS ---
    total_pnl = sum(t['pnl'] for t in trades)
    
    results["total_pnl"] = total_pnl
    results["trade_count"] = len(trades)
    results["trades"] = trades
    results["is_active"] = (current_holding is not None)
    results["status_message"] = f"Simulated PnL: ${total_pnl:,.2f} ({len(trades)} trades)"
    
    # Calculate ROI (Return on Investment)
    if fixed_share_size > 0:
        initial_invest = fixed_share_size * df['close'].iloc[0]
    else:
        initial_invest = investment_size
        
    if initial_invest > 0:
        results["total_return"] = total_pnl / initial_invest
        results["roi"] = results["total_return"]
    
    # --- STEP 5: BENCHMARKING (COMPARISON) ---
    stock_start_price = df['close'].iloc[0]
    stock_end_price = df['close'].iloc[-1]
    
    # Benchmark 1: What if we just bought the stock and held it?
    if stock_start_price > 0:
        if fixed_share_size > 0:
            bh_stock_shares = float(fixed_share_size)
            bh_inv_size = bh_stock_shares * stock_start_price
        else:
            bh_stock_shares = investment_size / stock_start_price
            bh_inv_size = investment_size
            
        bh_stock_final_value = bh_stock_shares * stock_end_price
        results["bh_stock_pnl"] = bh_stock_final_value - bh_inv_size
        results["bh_stock_buy"] = float(stock_start_price)
        results["bh_stock_sell"] = float(stock_end_price)
    
    # Benchmark 2: What if we bought the Market (S&P 500) instead?
    start_date = df.index[0]
    end_date = df.index[-1]
    
    if bench_df is not None and not bench_df.empty:
        bench_df = bench_df.sort_index(ascending=True)
        # Slice benchmark data to match the exact same date range as our strategy
        b_slice = bench_df[(bench_df.index >= start_date) & (bench_df.index <= end_date)]
        
        if not b_slice.empty:
            b_start = b_slice.iloc[0]['close']
            b_end = b_slice.iloc[-1]['close']
            
            if b_start > 0:
                # Invest the SAME Dollar Amount into the Benchmark
                bh_bench_shares = bh_inv_size / b_start
                bh_bench_final_value = bh_bench_shares * b_end
                
                results["bh_bench_pnl"] = bh_bench_final_value - bh_inv_size
                results["bh_bench_buy"] = float(b_start)
                results["bh_bench_sell"] = float(b_end)
                results["bh_bench_roi"] = (bh_bench_final_value - bh_inv_size) / bh_inv_size

    return results
