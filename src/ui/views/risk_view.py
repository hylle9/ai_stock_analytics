import streamlit as st
import pandas as pd
import plotly.express as px
from src.data.universe import UniverseManager
from src.data.ingestion import DataFetcher
from src.analytics.metrics import calculate_returns
from src.analytics.risk import calculate_risk_metrics

from src.models.portfolio import PortfolioManager, PortfolioStatus
from src.ui.views.portfolio_view import initialize_portfolio_manager

def render_risk_view():
    st.header("Risk Dashboard")
    
    # Initialize PM if needed
    initialize_portfolio_manager()
    
    # Selection Mode
    c_source, c_select = st.columns([1, 2])
    with c_source:
        source_type = st.radio("Source", ["Universe", "Portfolio"], horizontal=True)
    
    selected_tickers = []
    source_name = ""
    
    with c_select:
        if source_type == "Universe":
            manager = UniverseManager()
            universes = manager.list_universes()
            selected_universe = st.selectbox("Select Universe", universes)
            if selected_universe:
                u = manager.load_universe(selected_universe)
                selected_tickers = u.tickers
                source_name = selected_universe
        else:
            # Portfolio Mode
            pm: PortfolioManager = st.session_state.portfolio_manager
            # Filter non-archived
            active_portfolios = [p for p in pm.list_portfolios() if p.status != PortfolioStatus.ARCHIVED]
            
            if not active_portfolios:
                st.info("No active portfolios found. Create one in 'Portfolio' view.")
            else:
                port_map = {p.id: p.name for p in active_portfolios}
                selected_pid = st.selectbox("Select Portfolio", options=port_map.keys(), format_func=lambda x: port_map[x])
                if selected_pid:
                    p = pm.get_portfolio(selected_pid)
                    if p and p.holdings:
                        selected_tickers = list(p.holdings.keys())
                        source_name = p.name
                    elif p:
                        st.warning(f"Portfolio '{p.name}' has no holdings.")
    
    if selected_tickers:
        fetcher = DataFetcher()
        
        risk_data = []
        
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(selected_tickers):
            df = fetcher.fetch_ohlcv(ticker, period="1y")
            if not df.empty:
                returns = calculate_returns(df['close'])
                metrics = calculate_risk_metrics(returns)
                metrics['Ticker'] = ticker
                risk_data.append(metrics)
            progress_bar.progress((i + 1) / len(selected_tickers))
            
        if risk_data:
            risk_df = pd.DataFrame(risk_data)
            
            # Summary Metrics
            st.subheader(f"{source_name} Risk Profile")
            c1, c2, c3 = st.columns(3)
            c1.metric("Avg Volatility", f"{risk_df['Volatility_Ann'].mean():.2%}")
            c2.metric("Avg VaR (95%)", f"{risk_df['VaR_95'].mean():.2%}")
            c3.metric("Highest Risk", risk_df.loc[risk_df['Volatility_Ann'].idxmax(), 'Ticker'])
            
            # Scatter Plot: Return vs Risk (using Volatility as proxy for now, ideally Expected Return)
            # Since we don't have expected return yet, we'll plot Volatility vs VaR
            st.subheader("Risk Distribution")
            fig = px.scatter(risk_df, x="Volatility_Ann", y="VaR_95", text="Ticker", 
                             title="Volatility vs VaR (95%)",
                             labels={"Volatility_Ann": "Annualized Volatility", "VaR_95": "Value at Risk (95%)"})
            st.plotly_chart(fig, use_container_width=True)
            
            # Risk Table
            st.subheader("Detailed Risk Metrics")
            st.dataframe(risk_df.set_index("Ticker").style.format("{:.2%}"))
            
        else:
            st.warning("No data available for this universe.")
