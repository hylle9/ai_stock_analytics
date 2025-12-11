import streamlit as st
import pandas as pd
import sys
import os
import json

# --- 1. PATH CONFIGURATION ---
# Because this script is deep inside 'src/ui', we must add the project root to the python path.
# This allows us to import modules like 'src.data' or 'src.analytics' without errors.
# 'os.path.dirname(__file__)' gets the directory of this file.
# '..' goes up one level. We do it twice to get to the root.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# --- 2. MODULE IMPORTS ---
# We treat each "View" as a separate module to keep this main file clean.
from src.ui.views.universe_view import render_universe_view
from src.ui.views.stock_view import render_stock_view
from src.ui.views.risk_view import render_risk_view
from src.ui.views.robo_view import render_robo_view
from src.ui.views.portfolio_view import render_portfolio_view, initialize_portfolio_manager

from src.models.portfolio import PortfolioManager, PortfolioStatus
from src.utils.config import Config
from src.analytics.insights import InsightManager
from src.analytics.activity import ActivityTracker
from src.analytics.strategy_logic import calculate_strategy_signals
from src.data.ingestion import DataFetcher
from src.utils.profiling import Timer

# --- 3. COMMAND LINE ARGUMENTS ---
# We can start the app in different "modes" by passing flags.
# This is useful for testing without burning API credits.
# Usage: streamlit run app.py -- --synthetic
if "--synthetic" in sys.argv:
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "SYNTHETIC"
elif "--live" in sys.argv:
    # Prioritizes API calls over Database cache
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "LIVE"
elif "--production" in sys.argv:
    # Strict Live Data (no synthetic fallback)
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "PRODUCTION"

# --- 4. HELPER FUNCTIONS ---
def navigate_to_analysis(ticker):
    """
    Switch the view to 'Stock Analysis' and pre-select a ticker.
    This is used by buttons on the Dashboard.
    """
    st.session_state.analysis_ticker = ticker
    st.session_state.navigation_page = "Stock Analysis"

def render_sidebar():
    """Renders the side navigation menu and global status indicators."""
    with st.sidebar:
        st.title("AI Stock Lab")
        
        # Display current data mode so the user knows if data is real or fake
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

# --- 5. MAIN APPLICATION LOGIC ---
def main():
    # Configure the browser tab title and layout width
    st.set_page_config(layout="wide", page_title="AI Stock Lab")
    
    # Initialize the Portfolio System (loads portfolios from DB if needed)
    initialize_portfolio_manager()
    
    render_sidebar()
    
    # --- NAVIGATION STATE MANAGEMENT ---
    # Streamlit re-runs the entire script on every interaction.
    # We use 'st.session_state' to remember which page the user is on.
    if "navigation_page" not in st.session_state:
        st.session_state.navigation_page = "Dashboard"
        
    # The Radio Button controls the page selection.
    # key="navigation_page" binds this input directly to session_state.
    page = st.sidebar.radio(
        "Navigation", 
        ["Dashboard", "Stock Analysis", "Risk Dashboard", "Portfolio Management", "Robo Advisor", "Universe Management"], 
        key="navigation_page"
    )
    
    # --- DASHBOARD HEADER ---
    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.title("AI Stock Analytics Dashboard")
    with c_head2:
        # "Refresh Signals" Button:
        # This triggers a heavy batch calculation recalculating scores for all favorites.
        if st.button("🔄 Refresh Signals"):
            with st.spinner("Updating Strategy Signals & Scores..."):
                try:
                     # Lazy imports to avoid circular dependencies
                    from src.analytics.fusion import FusionEngine
                    from src.analytics.metrics import calculate_relative_volume, calculate_volume_acceleration
                    
                    tracker = ActivityTracker()
                    liked = tracker.get_liked_stocks()
                    fetcher = DataFetcher()
                    fusion = FusionEngine()
                    
                    count = 0
                    progress_bar = st.progress(0)
                    total = len(liked)
                    
                    # Loop through all liked stocks
                    for idx, item in enumerate(liked):
                        ticker = item['ticker']
                        # Fetch 1 year of data for calculations
                        df = fetcher.fetch_ohlcv(ticker, period="1y")
                        
                        if not df.empty:
                            # 1. Calculate Technical Signals (Buy/Sell)
                            signals = calculate_strategy_signals(df)
                            
                            # 2. Gather Inputs for Pressure Score
                            current_attention = 0.5 # Default
                            current_sentiment = 0.0 # Default
                            
                            # Try fetching "Alternative Data" (Social Volume)
                            try:
                                alt_df = fetcher.fetch_alt_data(ticker, days=5)
                                if not alt_df.empty:
                                    last_row = alt_df.iloc[-1]
                                    raw_att = last_row.get('Web_Attention', 0)
                                    current_attention = min(1.0, raw_att / 100.0)
                            except: pass
                            
                            # Try fetching News Sentiment
                            try: 
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
                            
                            # 3. Calculate New Pressure Score
                            score = fusion.calculate_pressure_score(
                                price_trend=norm_trend,
                                volatility_rank=0.5, # Placeholder
                                sentiment_score=current_sentiment,
                                attention_score=current_attention,
                                relative_volume=rel_vol,
                                volume_acceleration=vol_acc
                            )
                            
                            # 4. Save metadata back to DB
                            meta = item.get('metadata', {})
                            if isinstance(meta, str) and meta:
                                try: meta = json.loads(meta)
                                except: meta = {}
                            elif not isinstance(meta, dict):
                                meta = {}
                                
                            meta["strategy_rec"] = signals["strategy_rec"]
                            meta["strong_rec"] = signals["strong_rec"]
                            meta["score"] = score 
                            
                            tracker.update_ticker_metadata(ticker, meta)
                            count += 1
                        
                        progress_bar.progress((idx + 1) / total)
                    
                    st.success(f"Updated {count} stocks successfully!")
                    st.rerun() # Reload page to show new scores
                except Exception as e:
                    st.error(f"Batch Update Failed: {e}")

    # --- UI CONTAINERS ---
    # We use a mutable container 'dashboard_container' to isolate the Dashboard UI.
    # This allows us to call dashboard_container.empty() when switching pages,
    # ensuring no "Ghost UI Cards" remain on screen.
    dashboard_container = st.empty()

    if page == "Dashboard":
        with dashboard_container.container():
            st.write("---")
            
            # --- MARKET WEATHER (Global Sentiment) ---
            tracker = ActivityTracker()
        
            # Warning if Read-Only Mode (When DB is locked by another process)
            is_read_only = getattr(tracker, "read_only", False)
            if is_read_only:
                st.sidebar.warning("🔒 **Read-Only Mode**\nDCS is running in background. New actions (Likes) will not be saved.")
            
            fetcher = DataFetcher()
            fetcher.warmup_cache() # Pre-load common data

            weather = tracker.get_market_weather()
            if weather:
                w_score = weather.get("score", 50.0)
                w_status = weather.get("status", "NEUTRAL")
                
                # Visual Indicator (Emoji based on score)
                if w_score > 65: 
                    w_color = "green"; w_icon = "🔥"
                elif w_score < 35: 
                    w_color = "red"; w_icon = "❄️"
                else: 
                    w_color = "gray"; w_icon = "☁️"
                    
                st.info(f"### {w_icon} Global Market Weather: {w_status} ({w_score:.1f}/100)")
            
            if st.sidebar.button("Refresh Data"):
                st.rerun()

            # --- DATA FETCHING (BATCH OPTIMIZATION) ---
            # Instead of fetching stock data one-by-one in the loop (slow),
            # we gather all tickers we need and fetch them in one batch.
            
            # 1. Get tickers from "Favorites"
            liked_stocks = tracker.get_liked_stocks()
            
            all_tickers = []
            if liked_stocks:
                 all_tickers.extend([f['ticker'] for f in liked_stocks])
            
            # 2. Get tickers from "Rising Pressure" (Top viewed)
            rising_stocks = tracker.get_rising_pressure_stocks(limit=12)
            if rising_stocks:
                 all_tickers.extend([f['ticker'] for f in rising_stocks])
                 
            all_tickers.extend(["RSP", "SPY"]) # Always fetch Benchmarks
            all_tickers = list(set(all_tickers)) # Remove duplicates
            
            # 3. Execute Batch Fetch
            batch_data = {}
            if all_tickers:
                 batch_data = fetcher.fetch_batch_ohlcv(all_tickers, period="2y")

            # --- SECTION: FAVORITE STOCKS ---
            if liked_stocks:
                st.subheader("❤️ Favorite Stocks")
                st.caption("Your personally liked stocks.")
                
                # Grid Layout (4 columns)
                l_cols = st.columns(4)
                with Timer("Render:Favorites"):
                    for idx, fav in enumerate(liked_stocks):
                        ticker = fav['ticker']
                        # Retrieve pre-fetched data
                        df = batch_data.get(ticker, pd.DataFrame())
                        rsp_df = batch_data.get("RSP", pd.DataFrame())
                        
                        # Render Card in one of the 4 columns
                        with l_cols[idx % 4]:
                            with st.container():
                                # Generate Badge HTML based on Strategy Rec
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
                                
                                st.metric("Pressure", f"{score:.1f}", f"{diff:+.1f}")
                                
                                # Alpha Check (Is it beating the market?)
                                beat_market_html = "&nbsp;"
                                try:
                                    from src.analytics.market_comparison import calculate_market_alpha
                                    alpha = calculate_market_alpha(fav['ticker'], stock_df=df, benchmark_df=rsp_df)
                                    if alpha > 0:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                                    else:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                                except Exception: pass
                                st.markdown(beat_market_html, unsafe_allow_html=True)

                                # P/E Ratio Check
                                fund = fetcher.get_fundamentals(fav['ticker'], allow_fallback=False)
                                pe = fund.get('pe_ratio', 0)
                                pe_str = f"P/E: {pe:.1f}" if pe > 0 else "P/E: N/A"
                                st.caption(pe_str)

                                # "Analysis" Button -> Jumps to Stock Analysis page
                                st.button("Analysis", 
                                          key=f"liked_{fav['ticker']}",
                                          on_click=navigate_to_analysis,
                                          args=(fav['ticker'],))
            
            # --- SECTION: RISING STOCK PRESSURE ---
            if rising_stocks:
                st.subheader("📈 Rising Stock Pressure")
                st.caption("Top viewed stocks sorted by momentum (Current Score vs 3-Day Avg)")
                
                # Filter Radio Button
                f_mode = st.radio(
                    "Filter Recommendations:",
                    ["All", "Buy & Strong Buy", "Strong Buy Only"],
                    index=0,
                    horizontal=True,
                    label_visibility="collapsed"
                )

                # Filter Logic
                filtered_rising = []
                if f_mode == "All":
                    filtered_rising = rising_stocks
                elif f_mode == "Buy & Strong Buy":
                    filtered_rising = [s for s in rising_stocks if s.get("strategy_rec") == "BUY"]
                elif f_mode == "Strong Buy Only":
                    filtered_rising = [s for s in rising_stocks if s.get("strong_rec") == "YES"]

                if not filtered_rising:
                    st.info("No stocks match the selected filter.")
                
                # Render Grid
                f_cols = st.columns(4)
                with Timer("Render:Rising"):
                    for idx, fav in enumerate(filtered_rising):
                        ticker = fav['ticker']
                        df = batch_data.get(ticker, pd.DataFrame())
                        rsp_df = batch_data.get("RSP", pd.DataFrame())
                        
                        with f_cols[idx % 4]:
                            with st.container():
                                # (Same Badge/Metric Logic as above...)
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
                                st.metric("Pressure", f"{score:.1f}", f"{diff:+.1f}")

                                # Market Alpha
                                beat_market_html = "&nbsp;"
                                try:
                                    from src.analytics.market_comparison import calculate_market_alpha
                                    alpha = calculate_market_alpha(ticker, stock_df=df, benchmark_df=rsp_df)
                                    if alpha > 0:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                                    else:
                                        beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                                except Exception: pass
                                st.markdown(beat_market_html, unsafe_allow_html=True)
        
                                # Fundamentals
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

            # --- SECTION: PORTFOLIO RISK OVERVIEW ---
            if 'portfolio_manager' in st.session_state:
                pm = st.session_state.portfolio_manager
                live_portfolios = [p for p in pm.list_portfolios() if p.status.value == PortfolioStatus.LIVE.value]
                
                if live_portfolios:
                    from src.analytics.risk import calculate_risk_metrics
                    from src.ui.components import render_risk_gauge
                    
                    fetcher = DataFetcher()
                    st.subheader("Active Portfolio Risk Assessment")
                    
                    # Batch fetch for all stocks in all portfolios
                    all_p_tickers = []
                    for p in live_portfolios:
                        all_p_tickers.extend(list(p.holdings.keys()))
                    all_p_tickers = list(set(all_p_tickers))
                    
                    p_batch_data = {}
                    if all_p_tickers:
                        p_batch_data = fetcher.fetch_batch_ohlcv(all_p_tickers, period="1y")

                    cols = st.columns(len(live_portfolios))
                    
                    for idx, p in enumerate(live_portfolios):
                                # Reconstruct portfolio pricing data from the batch
                                port_dfs = {}
                                missing_tickers = []
                                
                                for t in p.holdings.keys():
                                    if t in p_batch_data:
                                        port_dfs[t] = p_batch_data[t]
                                    else:
                                        missing_tickers.append(t)
                                
                                # Fallback individual fetch
                                if missing_tickers:
                                    for t in missing_tickers:
                                         port_dfs[t] = fetcher.fetch_ohlcv(t, period="1y")

                                if not port_dfs:
                                    continue

                                # Create "Pro-Forma" Historical Portfolio Value Series
                                # We sum (Historical Price * Current Quantity) for every day
                                portfolio_series = pd.Series(dtype=float)
                                valid_data = True
                                
                                for ticker, qty in p.holdings.items():
                                    df = port_dfs.get(ticker)
                                    if df is None or df.empty:
                                        valid_data = False; break
                                    
                                    val_series = df['close'] * qty
                                    
                                    if portfolio_series.empty:
                                        portfolio_series = val_series
                                        portfolio_series = portfolio_series.add(val_series, fill_value=0)
                                
                                if valid_data and not portfolio_series.empty:
                                    # Calculate Risk Metrics on the Portfolio Curve
                                    p_returns = portfolio_series.pct_change().dropna()
                                    metrics = calculate_risk_metrics(p_returns)
                                    vol = metrics.get("Volatility_Ann", 0.0)
                                    
                                    # Convert Volatility to Safety Score (0-100)
                                    # Heuristic: 40% Volatility = 0 Score. 0% Volatility = 100 Score.
                                    safety_score = max(0.0, min(100.0, 100 * (1 - (vol / 0.4))))
                                    
                                    with cols[idx]:
                                        st.markdown(f"**{p.name}**")
                                        st.plotly_chart(render_risk_gauge(safety_score / 100, f"Safety: {safety_score:.0f}/100"), use_container_width=True)
                                        st.caption(f"Ann. Volatility: {vol:.1%}")
                                            
    # --- PAGE ROUTING ---
    # Based on the selected 'page' variable, we render the appropriate view function.
    # Note `dashboard_container.empty()`: This cleans up the Dashboard before showing the new view.
    elif page == "Stock Analysis":
        dashboard_container.empty()
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
