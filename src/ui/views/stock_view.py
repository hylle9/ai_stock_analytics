import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.data.ingestion import DataFetcher
from src.analytics.technical import add_technical_features
from src.analytics.metrics import calculate_returns, calculate_volatility

from src.models.forecasting import ForecastModel
from src.analytics.sentiment import SentimentAnalyzer
from src.analytics.fusion import FusionEngine
import plotly.express as px

def plot_stock_chart(df, ticker, forecast=None):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, subplot_titles=(f'{ticker} Price', 'Volume'),
                        row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df['open'],
                                 high=df['high'],
                                 low=df['low'],
                                 close=df['close'],
                                 name='OHLC'), row=1, col=1)

    # Forecast
    if forecast is not None:
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat'], line=dict(color='purple', width=2, dash='dash'), name='Forecast'), row=1, col=1)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_upper'], line=dict(color='rgba(128,0,128,0.2)', width=0), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_lower'], line=dict(color='rgba(128,0,128,0.2)', width=0), fill='tonexty', fillcolor='rgba(128,0,128,0.2)', name='Confidence'), row=1, col=1)

    # MA
    if 'sma_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_50'], line=dict(color='orange', width=1), name='SMA 50'), row=1, col=1)
    if 'sma_200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_200'], line=dict(color='blue', width=1), name='SMA 200'), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    return fig

def render_stock_view():
    st.header("Stock Analysis")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        ticker = st.text_input("Ticker", "AAPL").upper()
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=4)
        show_forecast = st.checkbox("Show Forecast (30d)", value=False)
        
    if ticker:
        fetcher = DataFetcher()
        df = fetcher.fetch_ohlcv(ticker, period=period)
        
        if not df.empty:
            # Add features
            df = add_technical_features(df)
            
            # Forecast
            forecast_df = None
            if show_forecast:
                with st.spinner("Generating forecast..."):
                    model = ForecastModel()
                    forecast_df = model.train_predict(df)
            
            # Metrics
            returns = calculate_returns(df['close'])
            vol = calculate_volatility(returns).iloc[-1]
            last_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            change = (last_price - prev_price) / prev_price
            
            # Display Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Price", f"${last_price:.2f}", f"{change:.2%}")
            m2.metric("Volatility (Ann.)", f"{vol:.2%}")
            m3.metric("Volume", f"{df['volume'].iloc[-1]:,}")
            
            # Tabs
            tab1, tab2 = st.tabs(["Price & Technicals", "Multi-Modal Signals"])
            
            with tab1:
                st.plotly_chart(plot_stock_chart(df, ticker, forecast_df), use_container_width=True)
                with st.expander("Raw Data"):
                    st.dataframe(df.tail(10))
                    
            with tab2:
                st.subheader("Multi-Modal Analysis")
                
                # Fetch Alt Data
                alt_data = fetcher.fetch_alt_data(ticker)
                news = fetcher.fetch_news(ticker)
                
                # Analyze Sentiment
                analyzer = SentimentAnalyzer()
                news_score = analyzer.analyze_news(news)
                
                # Calculate Pressure Score
                fusion = FusionEngine()
                
                # Normalize inputs for fusion (simplified)
                # Trend: RSI > 50 is positive
                rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
                trend_norm = (rsi - 50) / 50 # -1 to 1
                
                # Volatility: normalized against history (simplified)
                vol_norm = min(1.0, vol * 2) # Cap at 50% vol
                
                # Sentiment: already -1 to 1
                
                # Attention: normalized 0 to 1
                att_norm = alt_data['Web_Attention'].iloc[-1] / 100
                
                pressure_score = fusion.calculate_pressure_score(
                    price_trend=trend_norm,
                    volatility_rank=vol_norm,
                    sentiment_score=news_score,
                    attention_score=att_norm
                )
                
                # Display Score
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric("Pressure Score", f"{pressure_score:.1f}/100")
                    st.progress(pressure_score / 100)
                    
                    st.write("### Components")
                    st.write(f"**Trend (RSI):** {rsi:.1f}")
                    st.write(f"**News Sentiment:** {analyzer.get_sentiment_label(news_score)} ({news_score:.2f})")
                    st.write(f"**Web Attention:** {alt_data['Web_Attention'].iloc[-1]:.0f}/100")
                    
                with c2:
                    # Plot Alt Data
                    fig_alt = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Web_Attention'], name="Web Attention"), secondary_y=False)
                    fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Social_Sentiment'], name="Social Sentiment", line=dict(dash='dot')), secondary_y=True)
                    fig_alt.update_layout(title="Alternative Data Signals (30d)", height=300)
                    st.plotly_chart(fig_alt, use_container_width=True)
                
                # News Feed
                st.subheader("Latest News")
                for item in news[:5]:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    st.caption(f"{item['publisher']} • {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d %H:%M')}")

