import streamlit as st
import pandas as pd
import plotly.express as px
from src.models.portfolio import Portfolio, PortfolioManager, PortfolioStatus, Optimizer
from src.models.decision import Recommender
from src.data.universe import UniverseManager
from src.data.ingestion import DataFetcher
from src.analytics.activity import ActivityTracker

def initialize_portfolio_manager():
    if 'portfolio_manager' not in st.session_state or not hasattr(st.session_state.portfolio_manager, 'save_portfolio'):
        import importlib
        import src.models.portfolio
        importlib.reload(src.models.portfolio)
        from src.models.portfolio import PortfolioManager, PortfolioStatus
        
        pm = PortfolioManager()
        
        # Check if we have loaded portfolios, otherwise seed default
        existing_portfolios = pm.list_portfolios()
        if not existing_portfolios:
            p = pm.create_portfolio("Main Portfolio", 100000)
            p.update_holdings("AAPL", 100, 150.0)
            p.update_holdings("MSFT", 50, 250.0)
            p.status = PortfolioStatus.LIVE
            pm.save_portfolio(p)
            st.session_state.active_portfolio_id = p.id
        else:
            # Default to first one
            st.session_state.active_portfolio_id = existing_portfolios[0].id
            
        st.session_state.portfolio_manager = pm

def render_portfolio_view():
    initialize_portfolio_manager()
    pm: PortfolioManager = st.session_state.portfolio_manager
    
    # --- Sidebar: Portfolio Management ---
    st.sidebar.header("🗂 Portfolio Management")
    
    # Create New Portfolio
    with st.sidebar.expander("Create New Portfolio"):
        new_name = st.text_input("Name")
        initial_cash = st.number_input("Initial Cash", value=100000.0, step=1000.0)
        if st.button("Create"):
            if new_name:
                p = pm.create_portfolio(new_name, initial_cash)
                st.session_state.active_portfolio_id = p.id
                st.success(f"Created '{new_name}'!")
                st.rerun()
            else:
                st.error("Name required")
    
    # Portfolio Selector
    portfolios = pm.list_portfolios()
    if not portfolios:
        st.info("No portfolios. Create one to get started.")
        return

    # Map names to IDs for selectbox
    port_map = {p.id: f"{p.name} ({p.status.value})" for p in portfolios}
    
    # Handle deletion case where active_id might be gone
    if getattr(st.session_state, 'active_portfolio_id', None) not in port_map:
        st.session_state.active_portfolio_id = portfolios[0].id
        
    selected_id = st.sidebar.selectbox(
        "Select Portfolio", 
        options=port_map.keys(),
        format_func=lambda x: port_map[x],
        index=list(port_map.keys()).index(st.session_state.active_portfolio_id)
    )
    st.session_state.active_portfolio_id = selected_id
    
    # Load Active Portfolio
    portfolio = pm.get_portfolio(selected_id)
    if not portfolio:
        st.error("Portfolio not found.")
        st.rerun()
        
    # --- Main Area ---
    
    # Header & Status
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        st.title(f"💼 {portfolio.name}")
    with c2:
        # Status Switcher
        # Status Switcher
        # Fix: Use string values to avoid Enum identity issues during reload
        status_options = [s.value for s in PortfolioStatus]
        new_status_val = st.selectbox(
            "Status", 
            options=status_options,
            index=status_options.index(portfolio.status.value),
            label_visibility="collapsed"
        )
        new_status = PortfolioStatus(new_status_val)
        if new_status != portfolio.status:
            portfolio.status = new_status
            st.rerun()
    with c3:
        if st.button("Delete 🗑️", type="primary"):
            pm.delete_portfolio(portfolio.id)
            st.rerun()

    # Metrics
    manager = UniverseManager()
    universe = manager.load_universe("Big_Tech_10") # Default for pricing
    fetcher = DataFetcher()
    
    current_prices = {}
    
    # Fetch live prices for holdings even if not in universe
    all_tickers = list(set(list(portfolio.holdings.keys()) + universe.tickers))
    
    with st.spinner("Updating valuations..."):
        for ticker in all_tickers:
            df = fetcher.fetch_ohlcv(ticker, period="5d") # Short period for quick price
            if not df.empty:
                current_prices[ticker] = df['close'].iloc[-1]
    
    total_value = portfolio.get_value(current_prices)
    allocation = portfolio.get_allocation(current_prices)
    
    # Top Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Value", f"${total_value:,.2f}")
    m1.metric("Cash Balance", f"${portfolio.cash:,.2f}")
    m1.metric("Holdings Count", len(portfolio.holdings))
    
    # To avoid clutter, let's put it below Metrics but above Holdings List
    st.divider()
    
    # --- STRATEGY ANALYSIS ---
    st.subheader("Accumulated Yearly Strategy Gains (Portfolio)")
    st.caption("Simulate performance of your **exact held quantities** over the last 1 year.")
    
    from src.analytics.backtester import run_sma_strategy
    
    if st.button("RUN PORTFOLIO ANALYSIS 🚀", type="primary"):
        p_fetcher = DataFetcher()
        
        # Benchmark
        with st.spinner("Fetching Market Data..."):
            p_bench_df = p_fetcher.fetch_ohlcv("RSP", period="1y")

        # Accumulators
        total_p1 = 0.0 # Short Term
        total_p2 = 0.0 # Safety
        total_p3 = 0.0 # Strong
        total_bench = 0.0
        
        p_progress = st.progress(0)
        p_status = st.empty()
        p_log = []
        
        holdings_list = list(portfolio.holdings.items()) # [(ticker, qty), ...]
        
        for i, (ticker, qty) in enumerate(holdings_list):
            p_status.text(f"Analyzing {ticker} ({qty} shares)...")
            p_progress.progress((i + 1) / len(holdings_list))
            
            try:
                # Use held qty
                fixed_qty = int(qty)
                
                # Fetch
                df = p_fetcher.fetch_ohlcv(ticker, period="1y")
                
                if not df.empty and len(df) > 50:
                     if 'sma_20' not in df.columns:
                        try:
                            df['sma_20'] = df['close'].rolling(window=20).mean()
                            df['sma_50'] = df['close'].rolling(window=50).mean()
                            df['sma_200'] = df['close'].rolling(window=200).mean()
                        except Exception as e:
                            print(f"Error calc SMA for {ticker}: {e}")
                        
                     # Align Bench
                     sim_bench = pd.DataFrame()
                     if not p_bench_df.empty:
                         sim_bench = p_bench_df[p_bench_df.index.isin(df.index)]
                         
                     # Run Strategies (Fixed Shares Mode)
                     # 1
                     s1 = run_sma_strategy(df, sim_bench, trend_filter_sma200=False, fixed_share_size=fixed_qty)
                     # 2
                     s2 = run_sma_strategy(df, sim_bench, trend_filter_sma200=True, fixed_share_size=fixed_qty)
                     # 3
                     s3 = run_sma_strategy(df, sim_bench, trend_filter_sma200=True, min_trend_strength=0.15, fixed_share_size=fixed_qty)
                     
                     total_p1 += s1.get("total_pnl", 0.0)
                     total_p2 += s2.get("total_pnl", 0.0)
                     total_p3 += s3.get("total_pnl", 0.0)
                     total_bench += s1.get("bh_bench_pnl", 0.0)
                     
                     p_log.append({
                         "Ticker": ticker,
                         "Qty": fixed_qty,
                         "Short Term": s1.get("total_pnl", 0.0),
                         "Safety": s2.get("total_pnl", 0.0),
                         "StrongSafe": s3.get("total_pnl", 0.0),
                         "S&P500": s1.get("bh_bench_pnl", 0.0)
                     })
                else:
                    st.warning(f"Insufficient data for {ticker} (Rows: {len(df)}). Strategy skipped.")

            except Exception as e:
                st.error(f"Error {ticker}: {e}")
        
        p_status.text("Analysis Complete!")
        p_progress.empty()
        
        # Display Results
        st.write(f"### 💰 Portfolio Gains (Based on Current Holdings)")
        
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Short Term Trend", f"${total_p1:,.0f}")
        pc2.metric("Long Term Safety", f"${total_p2:,.0f}", delta=f"{total_p2 - total_p1:,.0f}")
        pc3.metric("Strong >15%", f"${total_p3:,.0f}", delta=f"{total_p3 - total_p1:,.0f}")
        pc4.metric("Buy & Hold S&P500", f"${total_bench:,.0f}")
        
        with st.expander("Detailed Portfolio Breakdown"):
             if p_log:
                 st.dataframe(pd.DataFrame(p_log).style.format("${:,.0f}", subset=["Short Term", "Safety", "StrongSafe", "S&P500"]))
             else:
                 st.info("No strategies could be simulated for the current holdings (insufficient data or no holdings).")

    st.divider()
    c_list, c_add = st.columns([2, 1])
    
    with c_list:
        st.subheader("Current Holdings")
        
        # Init Tracker
        tracker = ActivityTracker()

        if portfolio.holdings:
            # Create display DF
            holdings_data = []
            for t, qty in portfolio.holdings.items():
                price = current_prices.get(t, 0)
                val = qty * price
                
                # Fetch Rec
                state = tracker.get_ticker_state(t)
                rec = state.get("strategy_rec", "N/A")
                
                holdings_data.append({
                    "Ticker": t,
                    "Rec": rec,
                    "Qty": qty,
                    "Price": f"${price:,.2f}",
                    "Value": f"${val:,.2f}",
                    "Action": t # For button mapping
                })
            
            hdf = pd.DataFrame(holdings_data)
            
            # HEADER ROW
            h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1, 1, 1, 1])
            h1.markdown("**Ticker**")
            h2.markdown("**Rec**")
            h3.markdown("**Qty**")
            h4.markdown("**Price**")
            h5.markdown("**Value**")
            h6.markdown("**Action**")
            st.divider()

            # Custom table rendering
            for _, row in hdf.iterrows():
                cc1, cc2, cc3, cc4, cc5, cc6 = st.columns([1, 1, 1, 1, 1, 1])
                cc1.write(f"**{row['Ticker']}**")
                
                # Rec Badge
                r_val = row['Rec']
                if r_val == "BUY":
                    cc2.markdown(":green[**BUY**]")
                elif r_val == "SELL":
                    cc2.markdown(":red[**SELL**]")
                else:
                    cc2.caption("N/A")

                cc3.write(f"{row['Qty']}")
                cc4.write(row['Price'])
                cc5.write(row['Value'])
                if cc6.button("Sell All", key=f"sell_{row['Ticker']}"):
                    portfolio.remove_ticker(row['Ticker'], current_prices.get(row['Ticker'], 0))
                    pm.save_portfolio(portfolio)
                    st.rerun()
            st.divider()
        else:
            st.info("No holdings. Add some assets!")

    with c_add:
        st.subheader("Add / Update Position")
        with st.form("add_ticker_form"):
            t_input = st.text_input("Ticker Symbol").upper()
            q_input = st.number_input("Quantity (+ Buy / - Sell)", step=1)
            
            if st.form_submit_button("Submit Order"):
                if t_input and q_input != 0:
                    price = current_prices.get(t_input, 0)
                    if price == 0:
                         # Try fetch single if not in cache
                         d = fetcher.fetch_ohlcv(t_input, "1d")
                         if not d.empty:
                             price = d['close'].iloc[-1]
                    
                    if price > 0:
                        try:
                            portfolio.update_holdings(t_input, int(q_input), price)
                            pm.save_portfolio(portfolio)
                            st.success(f"Executed: {t_input} {q_input} @ ${price:.2f}")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Failed: {e}")
                    else:
                        st.error("Could not fetch price for ticker.")
                        
    # --- Opportunity Discovery ---
    st.divider()
    st.subheader("🔍 Opportunity Discovery")
    
    from src.data.relationships import RelationshipManager
    rm = RelationshipManager()
    
    if portfolio.holdings:
        # Check for unknown holdings
        unknown_holdings = [t for t in portfolio.holdings.keys() if not rm.get_info(t)]
        
        if unknown_holdings:
            st.info(f"We don't have relationship data for: {', '.join(unknown_holdings)}")
            cols_ai = st.columns(len(unknown_holdings))
            for i, t in enumerate(unknown_holdings):
                with cols_ai[i]:
                    if st.button(f"✨ Expand Knowledge: {t}", key=f"ai_exp_{t}"):
                         with st.spinner(f"Asking Gemini about {t}..."):
                             success = rm.expand_knowledge(t)
                             if success:
                                 st.success(f"Learned about {t}!")
                                 st.rerun()
                             else:
                                 st.error("Failed to expand knowledge. Check API Key.")
            st.divider()

        recs = rm.get_recommendations_for_portfolio(list(portfolio.holdings.keys()))
        
        tab_peers, tab_comps = st.tabs(["Industry Peers", "Direct Competitors"])
        
        def render_rec_card(item, key_suffix):
            with st.container():
                col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
                with col_r1:
                    st.markdown(f"**{item['ticker']}**")
                    st.caption(item['name'])
                with col_r2:
                    st.caption(item['reason'])
                with col_r3:
                    if st.button("Add", key=f"add_rec_{item['ticker']}_{key_suffix}"):
                        # Auto-add 10 shares
                        # Determine price
                        p_rec = current_prices.get(item['ticker'], 0)
                        if p_rec == 0:
                             d_rec = fetcher.fetch_ohlcv(item['ticker'], "1d")
                             if not d_rec.empty:
                                 p_rec = d_rec['close'].iloc[-1]
                        
                        if p_rec > 0:
                            portfolio.update_holdings(item['ticker'], 10, p_rec)
                            pm.save_portfolio(portfolio)
                            st.toast(f"Added 10 shares of {item['ticker']}!")
                            st.rerun()
                        else:
                            st.error("Price unavailable")
                st.divider()
        
        with tab_peers:
            if recs['peers']:
                for item in recs['peers']:
                    render_rec_card(item, "peer")
            else:
                st.info("No industry peers found for current holdings.")
                
        with tab_comps:
            if recs['competitors']:
                for item in recs['competitors']:
                    render_rec_card(item, "comp")
            else:
                st.info("No direct competitors found for current holdings.")
    else:
        st.info("Add holdings to see related opportunities.")

    # Robo-Advisor (Only show if LIVE or PAUSED)
    if portfolio.status != PortfolioStatus.ARCHIVED:
        st.divider()
        st.subheader("🤖 Robo-Advisor")
        if st.checkbox("Show Recommendations"):
             # Basic Robo logic setup
             risk_score = st.slider("Risk Tolerance", 1, 10, 5)
             st.info(f"Robo-advisor implementation would use Risk Score: {risk_score} to optimize allocations.")
    else:
        st.warning("Portfolio is Archived. Robo-Advisor disabled.")
