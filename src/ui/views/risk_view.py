import streamlit as st
import pandas as pd
import plotly.express as px
from src.data.universe import UniverseManager
from src.data.ingestion import DataFetcher
from src.analytics.metrics import calculate_returns
from src.analytics.risk import calculate_risk_metrics

def render_risk_view():
    st.header("Risk Dashboard")
    
    # Universe Selection
    manager = UniverseManager()
    universes = manager.list_universes()
    selected_universe = st.selectbox("Select Universe", universes)
    
    if selected_universe:
        u = manager.load_universe(selected_universe)
        fetcher = DataFetcher()
        
        risk_data = []
        
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(u.tickers):
            df = fetcher.fetch_ohlcv(ticker, period="1y")
            if not df.empty:
                returns = calculate_returns(df['close'])
                metrics = calculate_risk_metrics(returns)
                metrics['Ticker'] = ticker
                risk_data.append(metrics)
            progress_bar.progress((i + 1) / len(u.tickers))
            
        if risk_data:
            risk_df = pd.DataFrame(risk_data)
            
            # Summary Metrics
            st.subheader("Universe Risk Profile")
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
