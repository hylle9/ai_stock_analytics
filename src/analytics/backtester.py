import pandas as pd
from typing import Dict, List, Any

def run_sma_strategy(df: pd.DataFrame, bench_df: pd.DataFrame = None, investment_size: float = 100000.0, trend_filter_sma200: bool = False, min_trend_strength: float = 0.0, fixed_share_size: int = 0) -> Dict[str, Any]:
    """
    Simulates a Buy-and-Sell strategy based on SMA Crossovers.
    Can use FIXED CAPITAL (invest $X) or FIXED SHARES (buy N shares).
    """
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
    
    # Check basic columns
    if df.empty or 'sma_20' not in df.columns or 'sma_50' not in df.columns:
        return results
        
    # Check filter columns
    if trend_filter_sma200 and 'sma_200' not in df.columns:
        return results

    # Ensure chronological order
    df = df.sort_index(ascending=True)
    
    trades = []
    
    dates = df.index
    closes = df['close'].values
    sma20s = df['sma_20'].values
    sma50s = df['sma_50'].values
    sma200s = df['sma_200'].values if 'sma_200' in df.columns else None
    
    current_holding = None # Dict with 'buy_price', 'buy_date', 'shares', 'invested_capital'
    
    temp_trades_log = [] 
    
    for i in range(1, len(df)):
        prev_20 = sma20s[i-1]
        prev_50 = sma50s[i-1]
        curr_20 = sma20s[i]
        curr_50 = sma50s[i]
        
        if pd.isna(prev_20) or pd.isna(prev_50) or pd.isna(curr_20) or pd.isna(curr_50):
            continue
            
        date = dates[i]
        price = closes[i]
        
        # --- BUY LOGIC ---
        buy_signal = False
        buy_reason = "Standard"
        
        # 1. Standard Golden Cross
        if prev_20 <= prev_50 and curr_20 > curr_50:
            buy_signal = True
        
        # 2. Delayed Entry (Safety Strategy)
        elif trend_filter_sma200 and (curr_20 > curr_50) and current_holding is None:
             if sma200s is not None:
                 prev_200 = sma200s[i-1]
                 curr_200 = sma200s[i]
                 if not pd.isna(prev_200) and not pd.isna(curr_200):
                     # Rule: SMA200 Rising AND SMA20 Rising AND SMA50 Rising
                     sma200_rising = curr_200 > prev_200
                     sma20_rising = curr_20 > prev_20
                     sma50_rising = curr_50 > prev_50
                     
                     if sma200_rising and sma20_rising and sma50_rising:
                         buy_signal = True
                         buy_reason = "Delayed Entry"

        if buy_signal:
            # Check Trend Filter if Active (Applies to both Standard and Delayed)
            is_valid_buy = True
            if trend_filter_sma200:
                if sma200s is not None:
                     prev_200 = sma200s[i-1]
                     curr_200 = sma200s[i]
                     if not pd.isna(prev_200) and not pd.isna(curr_200):
                         if curr_200 <= prev_200:
                             is_valid_buy = False # Filtered Out
                     else:
                         is_valid_buy = False
                else:
                    is_valid_buy = False

            # Check Strength Filter (Alpha SMA50)
            if is_valid_buy and min_trend_strength > 0:
                if sma200s is not None:
                     curr_200 = sma200s[i]
                     if not pd.isna(curr_200) and curr_200 > 0:
                         # Alpha Score: (SMA50 - SMA200) / SMA200
                         strength = (curr_50 - curr_200) / curr_200
                         if strength <= min_trend_strength:
                             is_valid_buy = False
                     else:
                         is_valid_buy = False
                else:
                    is_valid_buy = False

            if is_valid_buy and current_holding is None:
                # Calculate shares based on Capital OR Fixed Size
                if fixed_share_size > 0:
                    shares_to_buy = float(fixed_share_size)
                    capital_needed = shares_to_buy * float(price)
                else:
                    shares_to_buy = investment_size / float(price)
                    capital_needed = investment_size
                
                current_holding = {
                    "type": "BUY",
                    "date": date,
                    "price": float(price),
                    "shares": shares_to_buy,
                    "invested_capital": capital_needed,
                    "reason": buy_reason
                }
                
                temp_trades_log.append(current_holding)
        
        # --- SELL LOGIC (Death Cross) ---
        elif prev_20 >= prev_50 and curr_20 < curr_50:
            if current_holding is not None:
                buy_record = current_holding
                
                # Sell ALL shares
                shares_sold = buy_record['shares']
                sell_value = shares_sold * float(price)
                
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
                
                current_holding = None

    # RULE CHECK: Close Open Position at Market
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
            "status": "OPEN" # Mark as open/unrealized
         }
         trades.append(trade_entry)
    
    if not trades:
        return results
        
    total_pnl = sum(t['pnl'] for t in trades)
    
    results["total_pnl"] = total_pnl
    results["trade_count"] = len(trades)
    results["trades"] = trades
    results["is_active"] = (current_holding is not None)
    results["status_message"] = f"Simulated PnL: ${total_pnl:,.2f} ({len(trades)} trades)"
    
    # Calculate Strategy ROI
    # Helper to track total capital employed or simply PnL / Initial
    # Simplest: PnL / Initial Investment
    if fixed_share_size > 0:
        initial_invest = fixed_share_size * df['close'].iloc[0]
    else:
        initial_invest = investment_size
        
    if initial_invest > 0:
        results["total_return"] = total_pnl / initial_invest
        results["roi"] = results["total_return"]
    
    # --- BENCHMARK COMPARISONS (Buy & Hold) ---
    stock_start_price = df['close'].iloc[0]
    stock_end_price = df['close'].iloc[-1]
    
    # 1. Stock Buy & Hold
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
    
    # 2. Benchmark Buy & Hold (Equivalent Investment Amount)
    # We use valid range benchmarks
    start_date = df.index[0]
    end_date = df.index[-1]
    
    if bench_df is not None and not bench_df.empty:
        bench_df = bench_df.sort_index(ascending=True)
        b_slice = bench_df[(bench_df.index >= start_date) & (bench_df.index <= end_date)]
        
        if not b_slice.empty:
            b_start = b_slice.iloc[0]['close']
            b_end = b_slice.iloc[-1]['close']
            
            if b_start > 0:
                # Use same investment size as Stock Buy & Hold (bh_inv_size)
                # If fixed shares, investment size was fixed_share_size * stock_start_price
                
                # So here we invest that SAME DOLLAR AMOUNT into Benchmark
                bh_bench_shares = bh_inv_size / b_start
                bh_bench_final_value = bh_bench_shares * b_end
                
                results["bh_bench_pnl"] = bh_bench_final_value - bh_inv_size
                results["bh_bench_buy"] = float(b_start)
                results["bh_bench_sell"] = float(b_end)
                results["bh_bench_roi"] = (bh_bench_final_value - bh_inv_size) / bh_inv_size

    return results
