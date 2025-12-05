import streamlit as st
import pandas as pd
import plotly.express as px
from src.models.portfolio import Portfolio, Optimizer
from src.models.decision import Recommender
from src.data.universe import UniverseManager
from src.data.ingestion import DataFetcher
from src.analytics.metrics import calculate_returns

# Mock session state for portfolio (in a real app, this would be a DB)
def initialize_portfolio_state():
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = Portfolio(initial_cash=100000)
        # Seed with some initial holdings
        st.session_state.portfolio.update_holdings("AAPL", 100, 150.0)
        st.session_state.portfolio.update_holdings("MSFT", 50, 250.0)

def render_portfolio_view():
    st.header("Portfolio & Robo-Advisor")
    
    initialize_portfolio_state()
    portfolio = st.session_state.portfolio
    manager = UniverseManager()
    
    # 1. Fetch Data & Calculate Current Value
    # For simplicity, we'll use the "Big_Tech_10" universe as our investable universe
    universe = manager.load_universe("Big_Tech_10")
    if not universe:
        st.error("Please create/load a universe first.")
        return

    fetcher = DataFetcher()
    current_prices = {}
    hist_data = {}
    
    with st.spinner("Fetching market data..."):
        for ticker in universe.tickers:
            df = fetcher.fetch_ohlcv(ticker, period="1y")
            if not df.empty:
                current_prices[ticker] = df['close'].iloc[-1]
                hist_data[ticker] = df['close']
    
    total_value = portfolio.get_value(current_prices)
    allocation = portfolio.get_allocation(current_prices)
    
    # 2. Dashboard Top Row
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"${total_value:,.2f}")
    c1.metric("Cash", f"${portfolio.cash:,.2f}")
    
    # Allocation Pie Chart
    alloc_df = pd.DataFrame(list(allocation.items()), columns=['Asset', 'Weight'])
    fig_pie = px.pie(alloc_df, values='Weight', names='Asset', title="Current Allocation")
    c2.plotly_chart(fig_pie, use_container_width=True)
    
    # 3. Robo-Advisor Section
    st.divider()
    st.subheader("🤖 Robo-Advisor Recommendations")
    
    c_risk, c_btn = st.columns([3, 1])
    risk_aversion = c_risk.slider("Risk Aversion (Higher = Safer)", 0.1, 10.0, 2.0, 0.1)
    
    if c_btn.button("Generate Recommendations"):
        # Prepare inputs for optimizer
        # Expected Returns: Simple historical mean (annualized)
        # Covariance: Historical covariance (annualized)
        
        prices_df = pd.DataFrame(hist_data)
        returns_df = prices_df.pct_change().dropna()
        
        expected_returns = returns_df.mean() * 252
        covariance = returns_df.cov() * 252
        
        optimizer = Optimizer()
        recommender = Recommender(optimizer)
        
        recs = recommender.generate_recommendations(
            portfolio, universe, current_prices, expected_returns, covariance, risk_aversion
        )
        
        if not recs.empty:
            st.success(f"Generated {len(recs)} recommendations!")
            st.dataframe(recs)
            
            # Apply Button (Simulation)
            if st.button("Apply All Trades (Simulation)"):
                for _, row in recs.iterrows():
                    qty = row['Shares'] if row['Action'] == 'BUY' else -row['Shares']
                    portfolio.update_holdings(row['Ticker'], qty, row['Price'])
                st.success("Trades executed successfully!")
                st.rerun()
        else:
            st.info("Portfolio is already optimal for this risk profile.")
