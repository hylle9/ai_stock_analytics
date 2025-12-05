import streamlit as st
import pandas as pd
from src.data.market_data import fetch_ohlcv
from src.features.technical import add_technical_features
from src.features.microstructure import add_microstructure_features

def render_dashboard():
    st.title("Market Overview")
    
    st.markdown("### 🚀 Top Retail Movers (RPS)")
    
    # Mock list of tickers for demo
    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GME", "AMC"]
    
    results = []
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        try:
            df = fetch_ohlcv(ticker, period="3mo")
            if not df.empty:
                df = add_technical_features(df)
                df = add_microstructure_features(df)
                
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                
                results.append({
                    "Ticker": ticker,
                    "Price": f"${latest['close']:.2f}",
                    "Change": f"{(latest['close'] - prev['close']) / prev['close'] * 100:.2f}%",
                    "RPS": f"{latest['rps_proxy']:.1f}",
                    "Volume Z": f"{latest['volume_z_score']:.2f}",
                    "Volatility": f"{latest['atr']:.2f}"
                })
        except Exception as e:
            st.error(f"Error processing {ticker}: {e}")
        
        progress_bar.progress((i + 1) / len(tickers))
            
    if results:
        df_results = pd.DataFrame(results)
        
        # Style the dataframe
        st.dataframe(
            df_results.style.background_gradient(subset=['RPS'], cmap='Reds'),
            use_container_width=True
        )
    else:
        st.warning("No data available.")

    st.markdown("---")
    st.markdown("### 🌡️ Market Heatmap")
    st.info("Heatmap visualization coming in Phase 2.")
