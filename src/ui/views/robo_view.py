import streamlit as st
from src.analytics.robo_advisor import RoboAdvisor
from src.models.portfolio import PortfolioManager
import pandas as pd

def render_robo_view():
    st.title("🤖 Robo Advisor")
    st.markdown("Automated market scanning for momentum signals and portfolio risks.")
    
    # Initialize
    pm = PortfolioManager()
    robo = RoboAdvisor()
    
    # Get all Portfolio Tickers
    all_portfolios = pm.list_portfolios()
    my_tickers = set()
    for p in all_portfolios:
        my_tickers.update(p.holdings.keys())
        
    my_tickers_list = list(my_tickers)
    
    # Helper to navigate
    def go_to_analysis(ticker):
        st.session_state["analysis_ticker"] = ticker
        st.session_state["navigation_page"] = "Stock Analysis"

    # Scan Market
    with st.spinner("Scanning market for signals..."):
        results = robo.scan_market(my_tickers_list)

    if not results:
        st.warning("No data available. Please ensure the database is populated (run Backfill or wait for DCS).")
        return

    # Columns
    col1, col2, col3 = st.columns(3)
    
    # 1. Rising (Portfolio)
    with col1:
        st.subheader("🟢 Riding the Wave")
        st.caption("Your stocks with Positive Momentum (SMA20 > SMA50)")
        
        rising = results.get("rising", [])
        if not rising:
            st.info("No rising stocks in portfolio.")
        
        for item in rising:
            with st.container(border=True):
                st.markdown(f"**{item['ticker']}**")
                st.markdown(f"Price: **${item['price']:.2f}**")
                st.markdown(f"Spread: **+{item['diff_pct']:.1f}%**")
                st.button("Analyze", key=f"btn_rise_{item['ticker']}", on_click=go_to_analysis, args=(item['ticker'],))

    # 2. Falling (Portfolio)
    with col2:
        st.subheader("🔴 Warning Signs")
        st.caption("Your stocks with Negative Momentum (SMA20 < SMA50)")
        
        falling = results.get("falling", [])
        if not falling:
            st.success("No falling stocks in portfolio!")
            
        for item in falling:
            with st.container(border=True):
                st.markdown(f"**{item['ticker']}**")
                st.markdown(f"Price: **${item['price']:.2f}**")
                st.markdown(f"Spread: **{item['diff_pct']:.1f}%**")
                st.button("Analyze", key=f"btn_fall_{item['ticker']}", on_click=go_to_analysis, args=(item['ticker'],))

    # 3. New Opportunities (Non-Portfolio)
    with col3:
        st.subheader("✨ New Opportunities")
        st.caption("Fresh Golden Crosses (Last 10 Days)")
        
        new_opps = results.get("new_opps", [])
        if not new_opps:
            st.info("No recent Golden Crosses found in universe.")
            
        for item in new_opps:
            with st.container(border=True):
                st.markdown(f"**{item['ticker']}**")
                st.markdown(f"Price: **${item['price']:.2f}**")
                days_ago = item.get('days_ago', 0)
                day_str = "Today" if days_ago == 0 else f"{days_ago} days ago"
                st.markdown(f"Crossed: **{day_str}**")
                st.button("Analyze", key=f"btn_new_{item['ticker']}", on_click=go_to_analysis, args=(item['ticker'],))
