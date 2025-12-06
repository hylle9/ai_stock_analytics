import streamlit as st
# Force Reload
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ui.views.universe_view import render_universe_view
from src.ui.views.stock_view import render_stock_view
from src.ui.views.risk_view import render_risk_view
from src.ui.views.portfolio_view import render_portfolio_view, initialize_portfolio_manager

from src.models.portfolio import PortfolioManager, PortfolioStatus


# Helper for programmatic navigation
def navigate_to_analysis(ticker):
    st.session_state.analysis_ticker = ticker
    st.session_state.navigation_page = "Stock Analysis"

def main():
    st.set_page_config(page_title="AI Stock Lab", layout="wide")
    initialize_portfolio_manager()
    
    st.sidebar.title("AI Stock Lab")
    
    # Ensure default
    if "navigation_page" not in st.session_state:
        st.session_state.navigation_page = "Dashboard"
        
    page = st.sidebar.radio("Navigation", ["Dashboard", "Stock Analysis", "Risk Dashboard", "Portfolio & Robo-Advisor", "Universe Management"], key="navigation_page")
    
    if page == "Dashboard":
        st.title("Market Dashboard")
        st.write("---")
        
        # --- EXPLICIT FAVORITES (LIKED) ---
        from src.analytics.activity import ActivityTracker
        from src.data.ingestion import DataFetcher
        tracker = ActivityTracker()
        fetcher = DataFetcher()
        
        liked_stocks = tracker.get_liked_stocks()
        
        if liked_stocks:
            st.subheader("❤️ Favorite Stocks")
            st.caption("Your personally liked stocks.")
            
            l_cols = st.columns(4)
            for idx, fav in enumerate(liked_stocks):
                with l_cols[idx % 4]:
                    with st.container():
                        st.markdown(f"**{fav['ticker']}**")
                        
                        score = fav['pressure_score']
                        diff = fav['rising_diff']
                        diff_str = f"{diff:+.1f}"
                        
                        st.metric("Pressure", f"{score:.1f}", diff_str, help="**Pressure Score Guide**\n\n- **High (>70):** Strong Buy / Momentum. Price likely > SMA50.\n- **Neutral (40-70):** Hold / Consolidating.\n- **Low (<40):** Sell / Weakness. Price likely < SMA200.\n\n*Relates to SMA50 vs SMA200 trend strength.*")
                        
                        # Market Beat Check
                        beat_market_html = "&nbsp;"
                        try:
                            from src.analytics.market_comparison import calculate_market_alpha
                            alpha = calculate_market_alpha(fav['ticker'])
                            if alpha > 0:
                                beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                            else:
                                beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                        except Exception:
                            pass
                        st.markdown(beat_market_html, unsafe_allow_html=True)

                        # P/E Ratio
                        fund = fetcher.get_fundamentals(fav['ticker'])
                        pe = fund.get('pe_ratio', 0)
                        pe_str = f"P/E: {pe:.1f}" if pe > 0 else "P/E: N/A"
                        st.caption(pe_str)

                        st.button("Analysis", 
                                  key=f"liked_{fav['ticker']}",
                                  on_click=navigate_to_analysis,
                                  args=(fav['ticker'],))
                    st.divider()
        
        # --- RISING PRESSURE (Activity Based) ---
        rising_stocks = tracker.get_rising_pressure_stocks(limit=12)
        
        if rising_stocks:
            st.subheader("📈 Rising Stock Pressure")
            st.caption("Top viewed stocks sorted by momentum (Current Score vs 3-Day Avg)")
            
            # Grid layout
            f_cols = st.columns(4)
            for idx, fav in enumerate(rising_stocks):
                with f_cols[idx % 4]:
                    with st.container():
                        st.markdown(f"**{fav['ticker']}**")
                        
                        # Score formatting
                        score = fav['pressure_score']
                        diff = fav['rising_diff']
                        diff_str = f"{diff:+.1f}"
                        
                        st.metric("Pressure", f"{score:.1f}", diff_str, help="**Pressure Score Guide**\n\n- **High (>70):** Strong Buy / Momentum. Price likely > SMA50.\n- **Neutral (40-70):** Hold / Consolidating.\n- **Low (<40):** Sell / Weakness. Price likely < SMA200.\n\n*Relates to SMA50 vs SMA200 trend strength.*")
                        
                        # Market Beat Check
                        beat_market_html = "&nbsp;"
                        try:
                            from src.analytics.market_comparison import calculate_market_alpha
                            alpha = calculate_market_alpha(fav['ticker'])
                            if alpha > 0:
                                beat_market_html = f'<span style="font-size: 0.8em; color: green">🚀 Beating Market (+{alpha:.1%})</span>'
                            else:
                                beat_market_html = f'<span style="font-size: 0.8em; color: red">📉 Losing to Market ({alpha:.1%})</span>'
                        except Exception:
                            pass
                        st.markdown(beat_market_html, unsafe_allow_html=True)

                        # P/E Ratio
                        fund = fetcher.get_fundamentals(fav['ticker'])
                        pe = fund.get('pe_ratio', 0)
                        pe_str = f"P/E: {pe:.1f}" if pe > 0 else "P/E: N/A"
                        st.caption(pe_str)
                        
                        st.button("Analysis", 
                                  key=f"rise_{fav['ticker']}",
                                  on_click=navigate_to_analysis,
                                  args=(fav['ticker'],))

                    st.divider()
        else:
             if not liked_stocks:
                 st.info("Start analyzing stocks to build your personalized favorites list!")
        
        st.write("---")

        if 'portfolio_manager' in st.session_state:
            pm = st.session_state.portfolio_manager
            # Fix: Compare values (strings) to avoid Enum reload identity mismatch
            live_portfolios = [p for p in pm.list_portfolios() if p.status.value == PortfolioStatus.LIVE.value]
            
            if not live_portfolios:
                st.info("No active portfolios found. Create one in 'Portfolio & Robo-Advisor'.")
            else:
                from src.data.ingestion import DataFetcher
                from src.analytics.risk import calculate_risk_metrics
                from src.ui.components import render_risk_gauge
                import pandas as pd
                
                fetcher = DataFetcher()
                
                st.subheader("Active Portfolio Risk Assessment")
                
                cols = st.columns(len(live_portfolios))
                
                for idx, p in enumerate(live_portfolios):
                    with cols[idx % 3]: # Wrap every 3
                        st.markdown(f"### {p.name}")
                        
                        if not p.holdings:
                            st.warning("No holdings to analyze.")
                            continue
                            
                        # Calculate Pro-Forma Historical Value
                        # Fetch 1y data for all assets
                        portfolio_series = pd.Series(dtype=float)
                        
                        with st.spinner(f"Analyzing {p.name}..."):
                            valid_data = True
                            for ticker, qty in p.holdings.items():
                                df = fetcher.fetch_ohlcv(ticker, period="1y")
                                if df.empty:
                                    st.error(f"Could not fetch data for {ticker}")
                                    valid_data = False
                                    break
                                
                                # Align to common index? For MVP assume mostly overlapping '1y'
                                # Multiply close by qty
                                val_series = df['close'] * qty
                                
                                if portfolio_series.empty:
                                    portfolio_series = val_series
                                else:
                                    # Add to total, align index
                                    portfolio_series = portfolio_series.add(val_series, fill_value=0)
                            
                            if valid_data and not portfolio_series.empty:
                                # Calculate Returns of the portfolio value
                                p_returns = portfolio_series.pct_change().dropna()
                                
                                # Metric
                                metrics = calculate_risk_metrics(p_returns)
                                vol = metrics.get("Volatility_Ann", 0.0)
                                
                                # Convert Volatility to Safety Score (0-100)
                                # Assumption: 0% vol = 100 Score, 50% vol = 0 Score
                                # Score = 100 * (1 - (vol / 0.5))
                                safety_score = max(0.0, min(100.0, 100 * (1 - (vol / 0.4))))
                                
                                # Render Gauge
                                st.plotly_chart(render_risk_gauge(safety_score / 100, f"Safety Score: {safety_score:.0f}/100"), use_container_width=True)
                                
                                st.caption(f"Annualized Volatility: {vol:.1%}")
                                
                                # Interpretation
                                if safety_score > 80:
                                    st.success("**Insight:** High Safety (Conservative).")
                                elif safety_score > 50:
                                    st.info("**Insight:** Moderate Risk (Balanced).")
                                else:
                                    st.error("**Insight:** Low Safety (High Risk).")
                                    
    elif page == "Stock Analysis":
        render_stock_view()
    elif page == "Risk Dashboard":
        render_risk_view()
    elif page == "Portfolio & Robo-Advisor":
        render_portfolio_view()
    elif page == "Universe Management":
        render_universe_view()

if __name__ == "__main__":
    main()
