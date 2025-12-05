import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.data.market_data import fetch_ohlcv
from src.features.technical import add_technical_features
from src.features.microstructure import add_microstructure_features
from src.models.forecaster import generate_forecast

def render_stock_view():
    st.title("Stock Detail Analysis")
    
    ticker = st.sidebar.text_input("Enter Ticker", value="AAPL").upper()
    
    if st.sidebar.button("Analyze"):
        with st.spinner(f"Analyzing {ticker}..."):
            df = fetch_ohlcv(ticker, period="2y")
            
            if df.empty:
                st.error(f"Could not fetch data for {ticker}")
                return
                
            # Feature Engineering
            df = add_technical_features(df)
            df = add_microstructure_features(df)
            
            # Forecasting
            forecast_results = generate_forecast(df)
            
            # --- Layout ---
            
            # Top Metrics
            latest = df.iloc[-1]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Price", f"${latest['close']:.2f}", f"{df['close'].pct_change().iloc[-1]*100:.2f}%")
            col2.metric("RPS (Retail)", f"{latest['rps_proxy']:.1f}", help="0-100 Retail Participation Score")
            col3.metric("Forecast (1D)", f"{forecast_results.get('return_1d', 0)*100:.2f}%")
            col4.metric("Confidence", f"{forecast_results.get('confidence_score', 0):.1f}%")
            
            # Charts
            tab1, tab2, tab3 = st.tabs(["Price & Forecast", "Behavioral (RPS)", "Technical"])
            
            with tab1:
                st.subheader("Price Forecast")
                if "forecast_df" in forecast_results:
                    f_df = forecast_results["forecast_df"]
                    
                    fig = go.Figure()
                    
                    # Historical Close
                    fig.add_trace(go.Scatter(x=df.index, y=df['close'], name="History", line=dict(color='blue')))
                    
                    # Forecast
                    fig.add_trace(go.Scatter(x=f_df['ds'], y=f_df['yhat'], name="Forecast", line=dict(color='green', dash='dash')))
                    fig.add_trace(go.Scatter(x=f_df['ds'], y=f_df['yhat_upper'], name="Upper Bound", line=dict(width=0), showlegend=False))
                    fig.add_trace(go.Scatter(x=f_df['ds'], y=f_df['yhat_lower'], name="Lower Bound", line=dict(width=0), fill='tonexty', fillcolor='rgba(0, 255, 0, 0.2)', showlegend=False))
                    
                    fig.update_layout(title=f"{ticker} Price Forecast", xaxis_title="Date", yaxis_title="Price")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Forecast not available.")

            with tab2:
                st.subheader("Retail Participation Signal (RPS)")
                
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig.add_trace(go.Bar(x=df.index, y=df['volume'], name="Volume", marker_color='lightgray'), secondary_y=False)
                fig.add_trace(go.Scatter(x=df.index, y=df['rps_proxy'], name="RPS", line=dict(color='red', width=2)), secondary_y=True)
                
                fig.update_layout(title="RPS vs Volume", xaxis_title="Date")
                fig.update_yaxes(title_text="Volume", secondary_y=False)
                fig.update_yaxes(title_text="RPS (0-100)", secondary_y=True)
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.info("RPS is currently a proxy based on Volume Anomalies and Volatility. Phase 2 will integrate true microstructure data.")

            with tab3:
                st.subheader("Technical Indicators")
                st.line_chart(df[['rsi', 'atr']])
