import pandas as pd
from src.data.ingestion import DataFetcher
import streamlit as st
from src.analytics.technical import add_technical_features

@st.cache_data(ttl=3600)
def calculate_market_alpha(ticker: str, stock_df: pd.DataFrame = None, benchmark_df: pd.DataFrame = None, period: str = "1y") -> float:
    """
    Calculates Alpha (Excess Return vs Benchmark) over the period.
    Simple Metric: (Ticker Return - Benchmark Return).
    Returns 0.0 if data is insufficient.
    Accepts pre-fetched DataFrames to avoid redundant API calls.
    """
    if stock_df is None or benchmark_df is None:
        return 0.0
    
    df = stock_df.copy() # Avoid mutating original
    bench_df = benchmark_df.copy()
    
    # Feature Engineer if needed (assuming batch fetch creates raw data)
    # Check if 'sma_50' exists, if not add it
    if 'sma_50' not in df.columns:
        df = add_technical_features(df)
    if 'sma_50' not in bench_df.columns:
        bench_df = add_technical_features(bench_df)
    
    # Slice benchmark to match stock start
    start_date = df.index.min()
    bench_df = bench_df[bench_df.index >= start_date]
    if bench_df.empty:
        return 0.0
        
    # 3. Calculate Growth (Logic copied from stock_view.py)
    # Stock
    s_growth = 0.0
    f_valid_date = None
    if 'sma_50' in df.columns:
        valid_s = df['sma_50'].dropna()
        if not valid_s.empty:
            f_valid_date = valid_s.index[0]
            s_start = valid_s.iloc[0]
            s_end = valid_s.iloc[-1]
            if s_start > 0:
                s_growth = (s_end - s_start) / s_start

    # Market
    m_growth = 0.0
    if 'sma_50' in bench_df.columns and f_valid_date:
        bslice = bench_df[bench_df.index >= f_valid_date]
        valid_b = bslice['sma_50'].dropna()
        if not valid_b.empty:
            b_start = valid_b.iloc[0]
            b_end = valid_b.iloc[-1]
            if b_start > 0:
                m_growth = (b_end - b_start) / b_start
                
    return s_growth - m_growth
