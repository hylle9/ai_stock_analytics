import streamlit as st
import pandas as pd
import plotly.express as px
from src.models.portfolio import Portfolio, PortfolioManager, PortfolioStatus, Optimizer
from src.models.decision import Recommender
from src.data.universe import UniverseManager
from src.data.ingestion import DataFetcher

def initialize_portfolio_manager():
    if 'portfolio_manager' not in st.session_state:
        pm = PortfolioManager()
        # Seed a default portfolio
        p = pm.create_portfolio("Main Portfolio", 100000)
        p.update_holdings("AAPL", 100, 150.0)
        p.update_holdings("MSFT", 50, 250.0)
        p.status = PortfolioStatus.LIVE
        st.session_state.portfolio_manager = pm
        st.session_state.active_portfolio_id = p.id

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
        new_status = st.selectbox(
            "Status", 
            options=[s for s in PortfolioStatus],
            format_func=lambda x: x.value,
            index=list(PortfolioStatus).index(portfolio.status),
            label_visibility="collapsed"
        )
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
    
    st.divider()
    
    # Holdings Management
    c_list, c_add = st.columns([2, 1])
    
    with c_list:
        st.subheader("Current Holdings")
        if portfolio.holdings:
            # Create display DF
            holdings_data = []
            for t, qty in portfolio.holdings.items():
                price = current_prices.get(t, 0)
                val = qty * price
                holdings_data.append({
                    "Ticker": t,
                    "Qty": qty,
                    "Price": f"${price:,.2f}",
                    "Value": f"${val:,.2f}",
                    "Action": t # For button mapping
                })
            
            hdf = pd.DataFrame(holdings_data)
            
            # Using columns for layout to add delete buttons manually since st.dataframe is read-only for now
            # Custom table rendering
            for _, row in hdf.iterrows():
                cc1, cc2, cc3, cc4, cc5 = st.columns([1, 1, 1, 1, 1])
                cc1.write(f"**{row['Ticker']}**")
                cc2.write(f"{row['Qty']}")
                cc3.write(row['Price'])
                cc4.write(row['Value'])
                if cc5.button("Sell All", key=f"sell_{row['Ticker']}"):
                    portfolio.remove_ticker(row['Ticker'], current_prices.get(row['Ticker'], 0))
                    st.rerun()
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
                            st.success(f"Executed: {t_input} {q_input} @ ${price:.2f}")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Failed: {e}")
                    else:
                        st.error("Could not fetch price for ticker.")

    # Robo-Advisor (Only show if LIVE or PAUSED)
    if portfolio.status != PortfolioStatus.ARCHIVED:
        st.divider()
        st.subheader("🤖 Robo-Advisor")
        if st.checkbox("Show Recommendations"):
             # Basic Robo logic setup
             risk_score = st.slider("Risk Tolerance", 1, 10, 5)
             st.info(f"Robo-advisor implementation would use Risk Score: {risk_score} to optimize allocations.")
             # (Keeping original robo logic minimized for this refactor to focus on Portfolio Management)
    else:
        st.warning("Portfolio is Archived. Robo-Advisor disabled.")
