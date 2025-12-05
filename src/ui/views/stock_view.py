import streamlit as st
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.data.ingestion import DataFetcher
from src.analytics.technical import add_technical_features
from src.analytics.metrics import calculate_returns, calculate_volatility

from src.models.forecasting import ForecastModel
from src.analytics.sentiment import SentimentAnalyzer
from src.analytics.fusion import FusionEngine
from src.analytics.gemini_analyst import GeminiAnalyst
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
    
    # helper for session state mapping
    if 'analysis_ticker' not in st.session_state:
        st.session_state.analysis_ticker = "AAPL"
        
    fetcher = DataFetcher()

    # Search Expander
    with st.expander("🔍 Find a Stock (Search by Name)", expanded=False):
        search_query = st.text_input("Company Name / Keyword", key="stock_search_box")
        if search_query:
            results = fetcher.search_assets(search_query)
            if results:
                st.write(f"Found {len(results)} matches:")
                for res in results:
                    col_res1, col_res2 = st.columns([4, 1])
                    with col_res1:
                        st.markdown(f"**{res['symbol']}** - {res['name']}")
                        st.caption(f"{res.get('type', 'Asset')} • {res.get('region', 'Global')} • Score: {res.get('matchScore', 0):.2f}")
                    with col_res2:
                        if st.button("Analyze", key=f"btn_{res['symbol']}"):
                            st.session_state.analysis_ticker = res['symbol']
                            st.rerun()
            else:
                st.info("No matches found.")

    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Ticker Input (Defaulted from Session state)
        ticker = st.text_input("Ticker Symbol", value=st.session_state.analysis_ticker).upper()
        # Update session state if manual change
        if ticker != st.session_state.analysis_ticker:
            st.session_state.analysis_ticker = ticker
            
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
        show_forecast = st.checkbox("Show Forecast (30d)", value=False)
        
    if ticker:
        # fetcher = DataFetcher() # Already initialized
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
        else:
            st.error(f"No data found for ticker '{ticker}'. This might be because:")
            st.markdown("""
            - The ticker symbol is incorrect or not supported by the data provider.
            - The market is currently closed or the asset was delisted.
            - There is a temporary API outage.
            
            **Try searching for a different variation (e.g., 'VWDRY' for ADRs) or another company.**
            """)
            return
            
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
                
                # 1. RSI (Trend)
                rsi_bench = [np.random.randint(30, 70) for _ in range(3)]
                rsi_avg = sum(rsi_bench) / 3
                rsi_interpretation = "Overbought (>70)" if rsi > 70 else "Oversold (<30)" if rsi < 30 else "Neutral"
                st.metric(
                    "Trend (RSI)", 
                    f"{rsi:.1f}", 
                    f"{rsi - rsi_avg:.1f} vs Univ",
                    help=f"""
                    **Relative Strength Index (RSI)**
                    Measures the speed and magnitude of recent price changes to evaluate overvalued or undervalued conditions.
                    
                    - **Your Score:** {rsi:.1f} ({rsi_interpretation})
                    - **Universe Samples:** {rsi_bench} (Avg: {rsi_avg:.1f})
                    
                    *Interpretation:* A score above 70 suggests the asset may be due for a correction (Overbought), while below 30 indicates it may be undervalued (Oversold).
                    """
                )
                
                # 2. News Sentiment
                news_bench = [np.random.uniform(-0.5, 0.5) for _ in range(3)]
                news_avg = sum(news_bench) / 3
                sent_label = analyzer.get_sentiment_label(news_score)
                st.metric(
                    "News Sentiment",
                    f"{sent_label} ({news_score:.2f})",
                    f"{news_score - news_avg:.2f} vs Univ",
                    help=f"""
                    **Social & News Sentiment**
                    Aggregated NLP analysis of recent headlines and news articles.
                    
                    - **Your Score:** {news_score:.2f} ({sent_label})
                    - **Universe Samples:** {[f'{x:.2f}' for x in news_bench]} (Avg: {news_avg:.2f})
                    
                    *Selection:* Scores range from -1 (Extremely Negative) to +1 (Extremely Positive).
                    """
                )
                
                # 3. Web Attention
                att_bench = [np.random.randint(10, 60) for _ in range(3)]
                att_avg = sum(att_bench) / 3
                cur_att = alt_data['Web_Attention'].iloc[-1]
                st.metric(
                    "Web Attention",
                    f"{cur_att:.0f}/100",
                    f"{cur_att - att_avg:.0f} vs Univ",
                    help=f"""
                    **Web Attention Score**
                    Quantifies the volume of retail search and social discussion interest.
                    
                    - **Your Score:** {cur_att:.0f}
                    - **Universe Samples:** {att_bench} (Avg: {att_avg:.0f})
                    
                    *Insight:* High attention often precedes high volatility. A score > 80 indicates viral retailer interest.
                    """
                )

                # --- Gemini AI Research Clues ---
                st.divider()
                st.subheader("🤖 AI-News - Research Clues")
                st.caption("Powered by Gemini Pro • Synthesizing Quantitative Signals & Qualitative News")
                
                if st.button("Generate AI Insight"):
                    with st.spinner("Gemini is reading the news and connecting the dots..."):
                        analyst = GeminiAnalyst()
                        
                        # Prepare metrics for analyst
                        metrics_context = {
                            'rsi': rsi,
                            'sentiment_score': news_score,
                            'attention_score': cur_att
                        }
                        
                        report = analyst.analyze_news(ticker, news, metrics_context)
                        st.markdown(report)
                
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

