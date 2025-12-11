import streamlit as st
import pandas as pd
# Force Reload
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ui.views.universe_view import render_universe_view
from src.ui.views.stock_view import render_stock_view
from src.ui.views.risk_view import render_risk_view
from src.ui.views.robo_view import render_robo_view
from src.ui.views.portfolio_view import render_portfolio_view, initialize_portfolio_manager

from src.models.portfolio import PortfolioManager, PortfolioStatus
import pandas as pd


# Helper for programmatic navigation
from src.utils.config import Config
from src.analytics.insights import InsightManager
from src.analytics.activity import ActivityTracker
from src.analytics.strategy_logic import calculate_strategy_signals
from src.data.ingestion import DataFetcher
# Parse Args for Synthetic Mode (Streamlit runs top to bottom)
if "--synthetic" in sys.argv:
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "SYNTHETIC"
elif "--live" in sys.argv:
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "LIVE"
elif "--production" in sys.argv:
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "PRODUCTION"

def navigate_to_analysis(ticker):
    st.session_state.analysis_ticker = ticker
    st.session_state.navigation_page = "Stock Analysis"

@st.cache_data(ttl=86400, show_spinner=False)
def get_cached_fundamentals(ticker: str):
    """Cached fetch for fundamentals (P/E, Market Cap). Changes slowly."""
    # Instantiate simpler fetcher/provider solely for this call to avoid hashing issues
    from src.data.ingestion import DataFetcher
    local_fetcher = DataFetcher()
    return local_fetcher.get_fundamentals(ticker)

def render_sidebar():
    with st.sidebar:
        st.title("AI Stock Lab")
        
        if Config.USE_SYNTHETIC_DB:
            if Config.DATA_STRATEGY == "PRODUCTION":
                st.success("🟢 Production Mode (Strict Live Data)")
            elif Config.DATA_STRATEGY == "LIVE":
                st.success("🟢 Live DB Mode (Prioritize API)")
            else:
                st.success("🟢 Synthetic DB Mode (Prioritize DB)")
        else:
             st.error("🔴 File Cache Mode (Legacy)")
             
        st.write("Navigation")

def main():
    from src.utils.profiling import Timer
    # Global Config for Page
    st.set_page_config(layout="wide", page_title="AI Stock Lab")
    initialize_portfolio_manager()
    
    render_sidebar()
    
    # Ensure default
    if "navigation_page" not in st.session_state:
        st.session_state.navigation_page = "Dashboard"
        
    page = st.sidebar.radio("Navigation", ["Dashboard", "Stock Analysis", "Risk Dashboard", "Portfolio Management", "Robo Advisor", "Universe Management"], key="navigation_page")
    
    # Main Dashboard Header
    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.title("AI Stock Analytics Dashboard")
    with c_head2:
        if st.button("🔄 Refresh Signals"):
            with st.spinner("Updating Strategy Signals & Scores..."):
                try:
                    # Imports for Calculation
                    from src.analytics.fusion import FusionEngine
                    from src.analytics.metrics import calculate_relative_volume, calculate_volume_acceleration
                    
                    tracker = ActivityTracker()
                    liked = tracker.get_liked_stocks()
                    fetcher = DataFetcher()
                    fusion = FusionEngine()
                    
                    count = 0
                    progress_bar = st.progress(0)
                    total = len(liked)
                    
                    for idx, item in enumerate(liked):
                        ticker = item['ticker']
                        # Fetch Data
                        df = fetcher.fetch_ohlcv(ticker, period="1y")
                        
                        if not df.empty:
                            # 1. Strategy Signals
                            signals = calculate_strategy_signals(df)
                            
                            # 2. Pressure Score Calculation (Restore Fusion Logic)
                            # fetch alt data for context
                            current_attention = 0.5
                            current_sentiment = 0.0
                            
                            try:
                                # Get latest alt data from DB cache
                                alt_df = fetcher.fetch_alt_data(ticker, days=5)
                                if not alt_df.empty:
                                    last_row = alt_df.iloc[-1]
                                    raw_att = last_row.get('Web_Attention', 0)
                                    current_attention = min(1.0, raw_att / 100.0)
                            except: pass
                            
                            try: 
                                # Get sentiment from news (lightweight)
                                news = fetcher.fetch_news(ticker, limit=5)
                                if news:
                                    s_scores = [n.get('sentiment_score', 0) for n in news if 'sentiment_score' in n]
                                    if s_scores:
                                        current_sentiment = sum(s_scores) / len(s_scores)
                            except: pass

                            # Calc Volume Metrics
                            rel_vol = calculate_relative_volume(df, window=20)
                            vol_acc = calculate_volume_acceleration(df, window=3)
                            
                            # Calc RSI normalized
                            current_rsi = signals.get("current_rsi", 50.0)
                            norm_trend = (current_rsi - 50) / 50.0 if current_rsi else 0.0
                            
                            # Full Fusion Score
                            score = fusion.calculate_pressure_score(
                                price_trend=norm_trend,
                                volatility_rank=0.5, # Placeholder (or calc std dev)
                                sentiment_score=current_sentiment,
                                attention_score=current_attention,
                                relative_volume=rel_vol,
                                volume_acceleration=vol_acc
                            )
                            
                            # Existing Meta
                            meta = item.get('metadata', {})
                            if isinstance(meta, str) and meta:
                                try: meta = json.loads(meta)
                                except: meta = {}
                            elif not isinstance(meta, dict):
                                meta = {}
                                
                            # Update Meta
                            meta["strategy_rec"] = signals["strategy_rec"]
                            meta["strong_rec"] = signals["strong_rec"]
                            meta["score"] = score # NEW Calculated Score
                            
                            tracker.update_ticker_metadata(ticker, meta)
                            count += 1
                        
                        progress_bar.progress((idx + 1) / total)
                    
                    
                    st.success(f"Updated {count} stocks successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Batch Update Failed: {e}")

    # Market Weather Report (Global Context)
    
    # Use a specific container for Dashboard to allow cleaner transitions (ghost card prevention)
    dashboard_container = st.empty()

    if page == "Dashboard":
        with dashboard_container.container():
            # The original st.title and st.write are now part of the new header structure
            # st.title("Market Dashboard") # This is replaced by "AI Stock Analytics Dashboard"
            st.write("---") # This line should remain for separation
            
            # --- MARKET WEATHER WIDGET ---
            # --- MARKET WEATHER WIDGET ---
            tracker = ActivityTracker()
        
            # Check Read-Only Status
            is_read_only = getattr(tracker, "read_only", False)
            if is_read_only:
                st.sidebar.warning("🔒 **Read-Only Mode**\nDCS is running in background. New actions (Likes) will not be saved.")
            
            # Re-enable this if we want to toggle live/synthetic from UI
            fetcher = DataFetcher()
            # Optimize: Pre-fetch dates for batch performance
            fetcher.warmup_cache()

            weather = tracker.get_market_weather()
            if weather:
                w_score = weather.get("score", 50.0)
                w_status = weather.get("status", "NEUTRAL")
                w_time = weather.get("last_updated", "")
                
                # Color logic
                if w_score > 65: 
                    w_color = "green"
                    w_icon = "🔥"
                elif w_score < 35: 
                    w_color = "red"
                    w_icon = "❄️"
                else: 
                    w_color = "gray"
                    w_icon = "☁️"
                    
                st.info(f"### {w_icon} Global Market Weather: {w_status} ({w_score:.1f}/100)")
            if st.sidebar.button("Refresh Data"):
                st.rerun()

            # --- BATCH PRE-FETCH ---
            # Collect all tickers needed for this view
            
            # 1. Favorites
            liked_stocks = tracker.get_liked_stocks()
            
            all_tickers = []
            if liked_stocks:
                 all_tickers.extend([f['ticker'] for f in liked_stocks])
            
            # 2. Rising
            rising_stocks = tracker.get_rising_pressure_stocks(limit=12) # Fetch list early for batching
            if rising_stocks:
                 all_tickers.extend([f['ticker'] for f in rising_stocks])
                 
            all_tickers.extend(["RSP", "SPY"]) # Ensure Benchmarks are present
            all_tickers = list(set(all_tickers)) # Unique
            
            # Fetch ALL data in one go
            batch_data = {}
            if all_tickers:
                 batch_data = fetcher.fetch_batch_ohlcv(all_tickers, period="2y")

            # --- EXPLICIT FAVORITES (LIKED) ---
            
            # liked_stocks already fetched above
            
            if liked_stocks:
                st.subheader("❤️ Favorite Stocks")
                st.caption("Your personally liked stocks.")
                
                l_cols = st.columns(4)
                with Timer("Render:Favorites"):
                    for idx, fav in enumerate(liked_stocks):
                        ticker = fav['ticker']
                        # Look up pre-fetched data
                        df = batch_data.get(ticker, pd.DataFrame())
                        rsp_df = batch_data.get("RSP", pd.DataFrame())
                        
                        with l_cols[idx % 4]:
                            with st.container():
                                # Strategy Badge
                                rec = fav.get("strategy_rec", "Unknown")
                                rec_html = ""
                                if rec == "BUY":
                                    rec_html = " <span style='background-color:green; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>BUY</span>"
                                elif rec == "SELL":
                                    rec_html = " <span style='background-color:red; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>SELL</span>"
                                else:
                                    rec_html = f" <span style='background-color:grey; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>{rec}</span>"
                                    
                                st.markdown(f"**{ticker}**{rec_html}", unsafe_allow_html=True)
                                
                                score = fav['pressure_score']
                                diff = fav['rising_diff']
                                diff_str = f"{diff:+.1f}"
                                
                                st.metric("Pressure", f"{score:.1f}", diff_str, help="**Pressure Score Guide**\n\n- **High (>70):** Strong Buy / Momentum. Price likely > SMA50.\n- **Neutral (40-70):** Hold / Consolidating.\n- **Low (<40):** Sell / Weakness. Price likely < SMA200.\n\n*Relates to SMA50 vs SMA200 trend strength.*")
                                
                                # Market Beat Check
                                beat_market_html = "&nbsp;"
                                try:
                                    with Timer(f"API:Alpha:{fav['ticker']}"):
                                        from src.analytics.market_comparison import calculate_market_alpha
                                        alpha = calculate_market_alpha(fav['ticker'], stock_df=df, benchmark_df=rsp_df)
                                    if alpha > 0:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                                    else:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                                except Exception:
                                    pass
                                st.markdown(beat_market_html, unsafe_allow_html=True)

                                # P/E Ratio
                                with Timer(f"API:Fundamentals:{fav['ticker']}"):
                                    fund = fetcher.get_fundamentals(fav['ticker'], allow_fallback=False)
                                pe = fund.get('pe_ratio', 0)
                                pe_str = f"P/E: {pe:.1f}" if pe > 0 else "P/E: N/A"
                                st.caption(pe_str)

                                st.button("Analysis", 
                                          key=f"liked_{fav['ticker']}",
                                          on_click=navigate_to_analysis,
                                          args=(fav['ticker'],))
            
            # --- RISING PRESSURE (Activity Based) ---
            # rising_stocks fetched early for batching
            
            if rising_stocks:
                st.subheader("📈 Rising Stock Pressure")
                st.caption("Top viewed stocks sorted by momentum (Current Score vs 3-Day Avg)")
                
                # Filter Controls
                f_mode = st.radio(
                    "Filter Recommendations:",
                    ["All", "Buy & Strong Buy", "Strong Buy Only"],
                    index=0,
                    horizontal=True,
                    label_visibility="collapsed"
                )

                filtered_rising = []
                if f_mode == "All":
                    filtered_rising = rising_stocks
                elif f_mode == "Buy & Strong Buy":
                    # BUY or Strong Buy (Assuming Strong implies Strategy Rec=BUY)
                    filtered_rising = [s for s in rising_stocks if s.get("strategy_rec") == "BUY"]
                elif f_mode == "Strong Buy Only":
                    filtered_rising = [s for s in rising_stocks if s.get("strong_rec") == "YES"]

                if not filtered_rising:
                    st.info("No stocks match the selected filter.")
                
                # Grid layout
                f_cols = st.columns(4)
                with Timer("Render:Rising"):
                    for idx, fav in enumerate(filtered_rising):
                        ticker = fav['ticker']
                        # Look up pre-fetched data
                        df = batch_data.get(ticker, pd.DataFrame())
                        rsp_df = batch_data.get("RSP", pd.DataFrame())
                        
                        with f_cols[idx % 4]:
                            with st.container():
                                # Strategy Badge
                                rec = fav.get("strategy_rec", "Unknown")
                                rec_html = ""
                                if rec == "BUY":
                                    rec_html = " <span style='background-color:green; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>BUY</span>"
                                elif rec == "SELL":
                                    rec_html = " <span style='background-color:red; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>SELL</span>"
                                else:
                                    rec_html = f" <span style='background-color:grey; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em'>{rec}</span>"

                                st.markdown(f"**{ticker}**{rec_html}", unsafe_allow_html=True)
                                
                                score = fav['pressure_score']
                                diff = fav['rising_diff']
                                diff_str = f"{diff:+.1f}"
                                
                                st.metric("Pressure", f"{score:.1f}", diff_str, help="**Pressure Score Guide**\n\n- **High (>70):** Strong Buy / Momentum. Price likely > SMA50.\n- **Neutral (40-70):** Hold / Consolidating.\n- **Low (<40):** Sell / Weakness. Price likely < SMA200.\n\n*Relates to SMA50 vs SMA200 trend strength.*")

                                # Market Beat Check
                                beat_market_html = "&nbsp;"
                                try:
                                    with Timer(f"API:Alpha:{ticker}"):
                                        from src.analytics.market_comparison import calculate_market_alpha
                                        alpha = calculate_market_alpha(ticker, stock_df=df, benchmark_df=rsp_df)
                                    if alpha > 0:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                                    else:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                                except Exception:
                                    pass
                                st.markdown(beat_market_html, unsafe_allow_html=True)
        
                                # P/E Ratio
                                with Timer(f"API:Fundamentals:{ticker}"):
                                    fund = fetcher.get_fundamentals(ticker, allow_fallback=False)
                                pe = fund.get('pe_ratio', 0)
                                pe_str = f"P/E: {pe:.1f}" if pe > 0 else "P/E: N/A"
                                st.caption(pe_str)
                                
                                st.button("Analysis", 
                                          key=f"rise_{ticker}",
                                          on_click=navigate_to_analysis,
                                          args=(ticker,))
            else:
                 if not liked_stocks:
                     st.info("Start analyzing stocks to build your personalized favorites list!")
            
            st.write("---")

            if 'portfolio_manager' in st.session_state:
                pm = st.session_state.portfolio_manager
                # Fix: Compare values (strings) to avoid Enum reload identity mismatch
                live_portfolios = [p for p in pm.list_portfolios() if p.status.value == PortfolioStatus.LIVE.value]
                
                if not live_portfolios:
                    st.info("No active portfolios found. Create one in 'Portfolio Management'.")
                else:
                    from src.analytics.risk import calculate_risk_metrics
                    from src.ui.components import render_risk_gauge

                    
                    fetcher = DataFetcher()
                    
                    st.subheader("Active Portfolio Risk Assessment")
                    
                    # BATCH FETCH for Portfolios
                    all_p_tickers = []
                    for p in live_portfolios:
                        all_p_tickers.extend(list(p.holdings.keys()))
                    all_p_tickers = list(set(all_p_tickers))
                    
                    p_batch_data = {}
                    if all_p_tickers:
                        # Risk calc uses 1y data usually
                        p_batch_data = fetcher.fetch_batch_ohlcv(all_p_tickers, period="1y")

                    cols = st.columns(len(live_portfolios))
                    
                    for idx, p in enumerate(live_portfolios):
                                   # Use batch data logic to assemble a dict of {ticker: df} for this portfolio
                                port_dfs = {}
                                missing_tickers = []
                                
                                # Original Loop was iterating keys only in my bad refactor
                                # We need both for the logic below, but first let's just assemble the DFs
                                for t in p.holdings.keys():
                                    if t in p_batch_data:
                                        port_dfs[t] = p_batch_data[t]
                                    else:
                                        missing_tickers.append(t)
                                
                                # Fallback for missing
                                if missing_tickers:
                                    for t in missing_tickers:
                                         port_dfs[t] = fetcher.fetch_ohlcv(t, period="1y")

                                if not port_dfs:
                                    st.warning("No data.")
                                    continue

                                # Calculate Pro-Forma Historical Value
                                portfolio_series = pd.Series(dtype=float)
                                valid_data = True
                                
                                # NOW we iterate items to get qty for value calculation
                                for ticker, qty in p.holdings.items():
                                    df = port_dfs.get(ticker)
                                    
                                    if df is None or df.empty:
                                        # specific logic if one ticker is missing from the batch source for some reason
                                        st.error(f"Could not fetch data for {ticker}")
                                        valid_data = False
                                        break
                                    
                                    # Multiply close by qty
                                    val_series = df['close'] * qty
                                    
                                    if portfolio_series.empty:
                                        portfolio_series = val_series
                                        portfolio_series = portfolio_series.add(val_series, fill_value=0)
                                
                                if valid_data and not portfolio_series.empty:
                                    # Calculate Returns of the portfolio value
                                    p_returns = portfolio_series.pct_change().dropna()
                                    
                                    # Metric
                                    metrics = calculate_risk_metrics(p_returns)
                                    vol = metrics.get("Volatility_Ann", 0.0)
                                    
                                    # Convert Volatility to Safety Score (0-100)
                                    safety_score = max(0.0, min(100.0, 100 * (1 - (vol / 0.4))))
                                    
                                    # Render Gauge
                                    st.plotly_chart(render_risk_gauge(safety_score / 100, f"Safety Score: {safety_score:.0f}/100"), use_container_width=True)
                                    
                                    st.caption(f"Annualized Volatility: {vol:.1%}")
                                    if safety_score > 80:
                                        st.success("**Insight:** High Safety (Conservative).")
                                    elif safety_score > 50:
                                        st.info("**Insight:** Moderate Risk (Balanced).")
                                    else:
                                        st.error("**Insight:** Low Safety (High Risk).")
                                            
    elif page == "Stock Analysis":
        dashboard_container.empty() # WIPE THE DASHBOARD ONLY
        render_stock_view()
    elif page == "Risk Dashboard":
        dashboard_container.empty()
        render_risk_view()
    elif page == "Portfolio Management":
        dashboard_container.empty()
        render_portfolio_view()
    elif page == "Robo Advisor":
        dashboard_container.empty()
        render_robo_view()
    elif page == "Universe Management":
        dashboard_container.empty()
        render_universe_view()

if __name__ == "__main__":
    main()
