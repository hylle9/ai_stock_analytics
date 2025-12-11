import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import subprocess
import webbrowser
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# Internal Modules
from src.data.ingestion import DataFetcher
from src.analytics.technical import add_technical_features
from src.utils.profiling import Timer
from src.analytics.backtester import run_sma_strategy
from src.analytics.metrics import calculate_returns, calculate_volatility, calculate_relative_volume, calculate_volume_acceleration
from src.models.forecasting import ForecastModel
from src.analytics.sentiment import SentimentAnalyzer
from src.analytics.fusion import FusionEngine
from src.analytics.gemini_analyst import GeminiAnalyst
from src.analytics.insights import InsightManager
from src.analytics.prompt_engineering import generate_deep_dive_prompt
from src.analytics.activity import ActivityTracker
from src.data.relationships import RelationshipManager
from src.utils import defaults
from src.utils.config import Config

# --- 1. CACHED DATA LOADERS ---
# Streamlit re-runs the script on every interaction. We MUST use caching (@st.cache_data)
# for heavy operations like data fetching, otherwise the app will be unresponsive.

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_technical_features(df):
    """
    Computes technical indicators (RSI, SMAs) on a dataframe.
    Cached for 1 hour so we don't re-compute if the input DF hasn't changed.
    """
    return add_technical_features(df)

@st.cache_data(ttl=3600, show_spinner=False)
def load_dashboard_data_v2(ticker: str):
    """
    Consolidated Data Loader mechanism.
    Instead of fetching bits and pieces scattered throughout the UI code,
    we fetch EVERYTHING needed for a complete view in one go.
    
    This improves performance (one latency hit) and robustness (no partial failures).
    
    Returns:
        Dictionary containing:
        - df_analysis: Historial price data with technicals
        - bench_df: Benchmark (S&P 500) data
        - news: Latest news articles
        - alt_data: Social sentiment/attention data
        - pressure_score: The calculated fusion score
        - components: Breakdown of the score (RSI, Volatility, etc)
        - ai_insight: Cached text analysis from Gemini
    """
    fetcher = DataFetcher()
    data = {
        "ticker": ticker,
        "valid": False,
        "df_analysis": pd.DataFrame(),
        "bench_df": pd.DataFrame(),
        "alt_data": pd.DataFrame(),
        "news": [],
        "news_score": 0.0,
        "pressure_score": 50.0,
        "components": {},
        "ai_insight": None,
        "deep_insight_weekly": None,
        "profile_error": None,
        "metrics": {},
        "sim_results": {} 
    }

    # STEP 1: Fetch Price History (Max available)
    # We fetch 'max' so we can do long-term SMA calculations (SMA200).
    df_analysis = fetcher.fetch_ohlcv(ticker, period="max")
    
    if df_analysis.empty:
        return data # Return empty valid=False if no data found
        
    data["valid"] = True
    
    # STEP 2: Calculate Technical Indicators
    # (Adds columns like 'sma_50', 'rsi', 'upper_band' to the dataframe)
    with Timer(f"TechFeatures:Main:{ticker}"):
        df_analysis = add_technical_features(df_analysis)
        
    # STEP 3: Fetch Benchmark Data (S&P 500 ETF 'RSP')
    # We use RSP (Equal Weight) instead of SPY as it's a better representation of the "average stock".
    bench_df = fetcher.fetch_ohlcv("RSP", period="max")
    if not bench_df.empty:
        with Timer("TechFeatures:Bench"):
             bench_df = add_technical_features(bench_df)
        
        # Align dates: Slice benchmark to start at the same time as our stock data
        start_date = df_analysis.index.min()
        bench_df = bench_df[bench_df.index >= start_date]
        data["bench_df"] = bench_df

    data["df_analysis"] = df_analysis

    # STEP 4: Fetch Alternative Data (Social & News)
    with Timer(f"API:AltData:{ticker}"):
        alt_data = fetcher.fetch_alt_data(ticker)
    data["alt_data"] = alt_data
    
    with Timer(f"API:News:{ticker}"):
        news = fetcher.fetch_news(ticker, limit=20)
    data["news"] = news

    # STEP 5: Calculate Scores (The "Brain")
    
    # A. Sentiment Analysis (Scan news headlines)
    with Timer("Analyzer:Sentiment"):
        analyzer = SentimentAnalyzer()
        news_score = analyzer.analyze_news(news)
    data["news_score"] = news_score
    
    # B. Fusion Engine (Pressure Score)
    fusion = FusionEngine()
    
    # Gather inputs for Fusion
    rsi = df_analysis['rsi'].iloc[-1] if 'rsi' in df_analysis.columns else 50
    
    # Helper to determine trend strength (e.g. are we above SMA50?)
    from src.analytics.metrics import calculate_trend_strength
    trend_norm = calculate_trend_strength(df_analysis)
    
    # Volatility
    returns = calculate_returns(df_analysis['close'])
    vol = calculate_volatility(returns).iloc[-1]
    vol_norm = min(1.0, vol * 2) # Normalize approx 0-50% vol to 0-1
    
    # Attention (Social)
    cur_att = alt_data['Web_Attention'].iloc[-1]
    att_norm = min(1.0, cur_att / 100.0)

    # Volume (Crowd Interest)
    rel_vol = calculate_relative_volume(df_analysis, window=20)
    vol_acc = calculate_volume_acceleration(df_analysis, window=3)

    # Compute Final Score
    with Timer("Analyzer:Fusion"):
        pressure_score = fusion.calculate_pressure_score(
            price_trend=trend_norm,
            volatility_rank=vol_norm,
            sentiment_score=news_score,
            attention_score=att_norm,
            relative_volume=rel_vol,
            volume_acceleration=vol_acc
        )
    data["pressure_score"] = pressure_score
    
    # Save the raw components so we can display them in the UI (e.g. "High Volatility", "Strong Trend")
    data["components"] = {
        "rsi": rsi,
        "vol": vol,
        "trend_norm": trend_norm,
        "vol_norm": vol_norm,
        "att_norm": att_norm,
        "rel_vol": rel_vol,
        "vol_acc": vol_acc,
        "cur_att": cur_att
    }
    
    # STEP 6: Peer Benchmarking
    # Find peer stocks to compare against (Company A vs Company B, C, D)
    peers = []
    try:
        with Timer(f"Peers:Init:{ticker}"):
            rm = RelationshipManager()
            
        with Timer(f"Peers:Query:{ticker}"):
            peers = rm.get_industry_peers(ticker, limit=4)
            # If no peers found in Graph Database, use generic fallback list
            if not peers:
                  peers = [t for t in defaults.DEFAULT_UNIVERSE_TICKERS if t != ticker][:4]
    except Exception as e:
        print(f"RM Error: {e}")
    
    rsi_vals = []
    sent_vals = []
    att_vals = []
    
    # Calculate average metrics for the peer group
    try:
        if peers:
            with Timer(f"Peers:Fetch:{ticker}"):
                 peer_results = fetcher.fetch_batch_ohlcv(peers, period="6mo")
            
            with Timer(f"Peers:Process:{ticker}"):
                for p in peers:
                    pdf = peer_results.get(p, pd.DataFrame())
                    if not pdf.empty:
                        try:
                            # Optimize: Slice only recent data for RSI calculation
                            if len(pdf) > 200:
                                pdf_slice = pdf.tail(200).copy()
                            else:
                                pdf_slice = pdf.copy()
                                
                            pdf_slice = add_technical_features(pdf_slice)
                            
                            if 'rsi' in pdf_slice.columns:
                                rsi_vals.append(pdf_slice['rsi'].iloc[-1])
                        except: pass
    except Exception as e:
        print(f"Peer Batch Error: {e}")

    def safe_avg(vals, default=50):
        return sum(vals) / len(vals) if vals else default

    # These averages serve as the "Baseline" for our gauges
    data["benchmarks"] = {
        "rsi_avg": safe_avg(rsi_vals, 50),
        "sent_avg": safe_avg(sent_vals, 0),
        "att_avg": safe_avg(att_vals, 0)
    }

    # STEP 7: AI Insights (Gemini)
    # We attempt to retrieve cached generated text to avoid API costs/latency.
    im = InsightManager()
    
    with Timer(f"InsightManager:Load:{ticker}"):
        # Check for "Weekly Deep Dive" (Valid for 7 days)
        cached_weekly = im.get_todays_insight(ticker, report_type="deep_research_weekly", valid_days=7)
        if cached_weekly and ("Rate Limit" in cached_weekly or "Quota" in cached_weekly):
             cached_weekly = None # Discard error messages so we can retry
        data["deep_insight_weekly"] = cached_weekly
        
        # Check for "Daily Snapshot" (Valid for 1 day)
        cached_daily = im.get_todays_insight(ticker, report_type="deep_dive", valid_days=1)
        data["ai_insight"] = cached_daily
        
        # Technical analysis text is loaded lazily in the UI
        data["technical_insight"] = None

    return data


# --- 2. PLOTTING FUNCTIONS ---

def plot_stock_chart(df, ticker, forecast=None, benchmark_df=None):
    """
    Creates the main interactive Plotly chart.
    Area 1 (Top): Candlesticks, Moving Averages, Benchmark Line, Crossover Markers.
    Area 2 (Bottom): Volume Bars.
    """
    # Create figure with 2 subplots sharing the X-axis (Dates)
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        subplot_titles=(f'{ticker} Price vs Market', 'Volume'),
        row_heights=[0.7, 0.3], # 70% Price, 30% Volume
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # A. Candlestick Chart (Open, High, Low, Close)
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='OHLC'
    ), row=1, col=1, secondary_y=False)

    # B. Forecast Overlay (Prophet)
    # Renders dashed line for prediction + shaded area for confidence interval
    if forecast is not None:
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat'], line=dict(color='purple', width=2, dash='dash'), name='Forecast'), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_upper'], line=dict(color='rgba(128,0,128,0.2)', width=0), showlegend=False), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_lower'], line=dict(color='rgba(128,0,128,0.2)', width=0), fill='tonexty', fillcolor='rgba(128,0,128,0.2)', name='Confidence'), row=1, col=1, secondary_y=False)

    # C. Moving Averages (The colorful lines)
    if 'sma_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_20'], line=dict(color='#ffd700', width=1), name='SMA 20 (Fast)'), row=1, col=1, secondary_y=False)
    if 'sma_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_50'], line=dict(color='orange', width=1), name='SMA 50 (Medium)'), row=1, col=1, secondary_y=False)
    if 'sma_200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_200'], line=dict(color='blue', width=1), name='SMA 200 (Trend)'), row=1, col=1, secondary_y=False)

    # D. Crossover Markers (Golden Cross / Death Cross)
    last_golden_cross_date = None

    def find_crossovers(fast, slow, name):
        """Identifies where two lines cross."""
        nonlocal last_golden_cross_date
        if fast.isna().all() or slow.isna().all(): return
        
        diff = fast - slow
        # Find points where the sign of difference changes (Positive <-> Negative)
        signs = np.sign(diff)
        sign_change = ((np.roll(signs, 1) - signs) != 0) & (signs != 0)
        sign_change[0] = False # Ignore first point noise
        
        crossover_dates = df.index[sign_change]
        crossover_vals = slow[sign_change]
        
        if len(crossover_dates) > 0:
            for d, v in zip(crossover_dates, crossover_vals):
                is_golden = diff.loc[d] > 0
                color = 'green' if is_golden else 'red'
                
                # Plot Marker
                fig.add_trace(go.Scatter(
                    x=[d], y=[v],
                    mode='markers',
                    marker=dict(symbol='circle', size=14, color=color, line=dict(color='white', width=1)),
                    name=f"{name} {'Bull' if is_golden else 'Bear'}",
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=f"{d.date()} | {name} {'Bull' if is_golden else 'Bear'}"
                ), row=1, col=1, secondary_y=False)
                
                if name == "Signal" and is_golden:
                    if last_golden_cross_date is None or d > last_golden_cross_date:
                        last_golden_cross_date = d

    # Run Crossover Logic: SMA 20 vs 50
    find_crossovers(df['sma_20'], df['sma_50'], "Signal")
    
    # Run Major Trend Crossover: SMA 50 vs 200 (Diamonds)
    def find_major_crossovers(fast, slow, name):
        if fast.isna().all() or slow.isna().all(): return
        diff = fast - slow
        signs = np.sign(diff)
        sign_change = ((np.roll(signs, 1) - signs) != 0) & (signs != 0)
        sign_change[0] = False
        crossover_dates = df.index[sign_change]
        crossover_vals = slow[sign_change]
        
        if len(crossover_dates) > 0:
             fig.add_trace(go.Scatter(
                x=crossover_dates, 
                y=crossover_vals,
                mode='markers',
                marker=dict(symbol='diamond', size=12, color='purple', line=dict(color='white', width=1)),
                name=f'{name} Cross',
                legendgroup='major_cross'
            ), row=1, col=1, secondary_y=False)

    find_major_crossovers(df['sma_50'], df['sma_200'], "Major Trend (50/200)")

    # E. Benchmark Line
    if benchmark_df is not None and 'sma_200' in benchmark_df.columns:
        fig.add_trace(go.Scatter(x=benchmark_df.index, y=benchmark_df['sma_200'], 
                               line=dict(color='#9370DB', width=3), # Medium Purple
                               name='S&P Market Trend (Indexed)'), 
                      row=1, col=1, secondary_y=False)

    # F. Volume Bars (Bottom Subplot)
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume'), row=2, col=1)

    # G. Layout Config
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="Price & S&P (RSP)", secondary_y=False, row=1, col=1)
    
    return fig, last_golden_cross_date


# --- 3. MAIN RENDER FUNCTION ---
def render_stock_view():
    """
    Renders the entire 'Stock Analysis' page.
    This function is called by app.py when the user navigates here.
    """
    st.header("Stock Analysis")
    
    # Initialize Session State
    if 'analysis_ticker' not in st.session_state:
        st.session_state.analysis_ticker = "AAPL"
        
    fetcher = DataFetcher()

    # --- UI COMPONENT: SEARCH BAR ---
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

    # --- UI COMPONENT: TICKER ENTRY & CONTROLS ---
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Ticker Box & Like Button
        c_tick, c_like = st.columns([3, 1])
        with c_tick:
            ticker = st.text_input("Ticker Symbol", value=st.session_state.analysis_ticker).upper().strip()
        with c_like:
            st.text(" ")
            st.text(" ")
            tracker = ActivityTracker()
            is_liked = tracker.is_liked(ticker)
            label = "❤️" if is_liked else "🤍"
            if st.button(label, key="like_btn", use_container_width=True):
                tracker.toggle_like(ticker)
                st.rerun()
                
        if ticker != st.session_state.analysis_ticker:
            st.session_state.analysis_ticker = ticker
            
        show_forecast = st.checkbox("Show Forecast (30d)", value=False)

        # Portfolio Quick-Add Widget
        if 'portfolio_manager' in st.session_state:
            pm = st.session_state.portfolio_manager
            portfolios = pm.list_portfolios()
            
            if portfolios:
                with st.expander("📂 Add to Portfolio"):
                    p_names = [p.name for p in portfolios]
                    selected_p_name = st.selectbox("Select Portfolio", p_names)
                    selected_p = next((p for p in portfolios if p.name == selected_p_name), None)
                    
                    c_shares, c_price = st.columns(2)
                    with c_shares:
                        shares = st.number_input("Shares", min_value=1, value=10)
                    with c_price:
                        cost_basis = st.number_input("Avg Cost", min_value=0.0, value=0.0, step=0.1)
                        
                    if st.button("Add Position"):
                        if selected_p:
                            try:
                                selected_p.update_holdings(ticker, shares, cost_basis)
                                st.toast(f"Added {shares} {ticker} to {selected_p_name}!", icon="✅")
                            except Exception as e:
                                st.error(f"Error: {e}")
            else:
                 st.caption("Create a portfolio first to add stocks.")
        
    if ticker:
        alpha_banner = st.empty() # Placeholder for "Beating Market" banner
        
        # --- DATA LOADING (Triggers the big function) ---
        if st.sidebar.button("🔄 Force Refresh Data"):
             st.toast("Clearing cache and refreshing...", icon="♻️")
             with st.spinner("Refetching data..."):
                 f = DataFetcher()
                 f.fetch_ohlcv(ticker, period="max", use_cache=False)
                 st.cache_data.clear()
                 st.rerun()

        with st.spinner(f"Analyzing {ticker}..."):
            with Timer(f"StockView:LoadData:{ticker}"):
                dashboard_data = load_dashboard_data_v2(ticker)
        
        if dashboard_data['df_analysis'].empty:
             st.error(f"No data found for ticker '{ticker}'.")
             return

        # Unpack loaded data for easier access
        df_analysis = dashboard_data["df_analysis"]
        bench_df = dashboard_data["bench_df"]
        alt_data = dashboard_data["alt_data"]
        news = dashboard_data["news"]
        pressure_score = dashboard_data["pressure_score"]
        news_score = dashboard_data["news_score"]
        comps = dashboard_data["components"]
        
        # Show Data Source Info (Live vs Synthetic)
        source_tag = df_analysis.attrs.get("source", "⚪ UNKNOWN")
        st.caption(f"Data Source: {source_tag}")

        # Forecast Logic
        forecast_df = None
        if show_forecast:
            with st.spinner("Generating forecast..."):
                model = ForecastModel()
                forecast_df = model.train_predict(df_analysis)
        
        # --- METRICS ROW ---
        last_price = df_analysis['close'].iloc[-1]
        prev_price = df_analysis['close'].iloc[-2]
        change = (last_price - prev_price) / prev_price
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Price", f"${last_price:.2f}", f"{change:.2%}")
        m2.metric("Volatility (Ann.)", f"{comps['vol']:.2%}")
        m3.metric("Volume", f"{df_analysis['volume'].iloc[-1]:,}")

        # pre-calc locals for logic
        vol_acc = comps.get("vol_acc", 0)
        rel_vol = comps.get("rel_vol", 0)
        att_norm = comps.get("att_norm", 0)
        cur_att = comps.get("cur_att", 0)
        rsi = comps.get("rsi", 50)

        # --- SECTION: MULTI-MODAL ANALYSIS (The "Hero" Section) ---
        st.subheader("Multi-Modal Analysis")
        
        tp_col1, tp_col2 = st.columns([1, 2])
        with tp_col1:
            # Display the Pressure Score Gauge
            st.metric(
                "Pressure Score", 
                f"{pressure_score:.1f}/100",
                help="Composite index tracking Price, Sentiment, Retail Interest, and Volatility."
            )
            st.progress(pressure_score / 100)
            
            # Show a textual label explaining WHY the score is high
            retail_msg = ""
            if vol_acc > 0.05:
                retail_msg = "🚀 Volume Accelerating!"
            elif rel_vol > 1.2:
                retail_msg = "🔥 High Volume Anomaly"
            elif att_norm > 0.2:
                retail_msg = "🗣️ High Social Chatter"
            
            if retail_msg:
                st.caption(f"{retail_msg}")

            st.info("""**Interpretation:**\n- **> 75 (Bullish):** High buying pressure.\n- **< 25 (Bearish):** High selling pressure.""")

        with tp_col2:
             # Plot Alternative Data (Web Attention & Social Sentiment)
            fig_alt = make_subplots(specs=[[{"secondary_y": True}]])
            fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Web_Attention'], name="Web Attention"), secondary_y=False)
            fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Social_Sentiment'], name="Social Sentiment", line=dict(dash='dot')), secondary_y=True)
            fig_alt.update_layout(title="Alternative Data Signals (30d)", height=250, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_alt, use_container_width=True)

        st.markdown("---")
        
        # --- AI INSIGHT (GEMINI) ---
        st.subheader("First-Class AI Insight")
        st.caption("Qualitative Analysis of Multi-Modal Signals")
        
        cached_weekly = dashboard_data["deep_insight_weekly"]
        cached_daily = dashboard_data["ai_insight"]

        if cached_weekly:
             st.info(f"🧬 **Deep Research Report** (Cached < 7 days)")
             st.markdown(cached_weekly)
        elif cached_daily:
            st.success(f"Standard Analysis from {datetime.now().strftime('%Y-%m-%d')} (Cached)")
            st.markdown(cached_daily)
        else:
            # Auto-Generate if missing (First time view)
            with st.spinner("🤖 Gemini is analyzing news & fundamentals..."):
                try:
                    analyst = GeminiAnalyst()
                    # Context package for prompt
                    metrics_context = {
                        'rsi': rsi,
                        'sentiment_score': news_score,
                        'attention_score': cur_att,
                        'pressure_score': pressure_score
                    }
                    report = analyst.analyze_news(ticker, news, metrics_context)
                    
                    if "Error" not in report:
                        im = InsightManager()
                        im.save_insight(ticker, report, report_type="deep_dive")
                        st.markdown(report)
                    else:
                        st.warning(f"AI could not generate report: {report}")
                except Exception as e:
                    st.warning(f"AI Generation failed: {e}")

        # "Deep Research" Button Upgrade
        st.write("#### 🧬 Need Deeper Answers?")
        if st.button("Run Deep Research (Gemini 1.5 Pro)"):
             with st.spinner("🕵️‍♂️ Conducting Deep Research (Industry, Competitors, Future)... This may take 30-60s."):
                analyst = GeminiAnalyst()
                metrics_context = {
                    'rsi': rsi,
                    'sentiment_score': news_score,
                    'attention_score': cur_att,
                    'pressure_score': pressure_score
                }
                deep_report = analyst.perform_deep_research(ticker, news, metrics_context)
                
                if "Error" not in deep_report:
                    im = InsightManager() 
                    im.save_insight(ticker, deep_report, report_type="deep_research_weekly")
                    st.rerun()
                else:
                    st.error(deep_report)
        
        # --- SECTION: PRICE & TECHNICALS ---
        st.divider()
        st.header("Price & Technicals")
        
        # Chart Timeframe Selector
        chart_period = st.radio("Timeframe", 
                              options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                              index=3, # Default 1y
                              horizontal=True,
                              key="chart_period_selector")
        
        # Slicing Logic for the Chart
        def slice_period(df, period):
            if df.empty or period == "max": return df
            days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
            days = days_map.get(period, 365)
            start_date = df.index.max() - pd.Timedelta(days=days)
            return df[df.index >= start_date]

        chart_df = slice_period(df_analysis, chart_period)
        
        # Prepare Benchmark Plot Data
        bench_plot_df = pd.DataFrame()
        if not bench_df.empty:
             bench_plot_df = bench_df[bench_df.index.isin(chart_df.index)].copy()
             # VISUAL TRICK: Normalize benchmark start price to match stock start price
             # This makes the lines start at the same point so you can compare slope/performance easily.
             if not bench_plot_df.empty and 'sma_200' in bench_plot_df.columns:
                 s_start = chart_df['sma_50'].iloc[0] if 'sma_50' in chart_df.columns else chart_df['close'].iloc[0]
                 b_start = bench_plot_df['sma_200'].iloc[0]
                 if b_start > 0 and s_start > 0:
                     ratio = s_start / b_start
                     bench_plot_df['sma_200'] = bench_plot_df['sma_200'] * ratio
        
        # Render the Plotly Chart
        with Timer("StockView:PlotChart"):
            fig, last_cross_date = plot_stock_chart(chart_df, ticker, forecast_df, benchmark_df=bench_plot_df)
            
        st.plotly_chart(fig, key=f"chart_{ticker}_{chart_period}", use_container_width=True)
            
        # --- SECTION: STRATEGY BACKTEST SIMULATION ---
        st.markdown("### 🧬 Strategy Simulations")
        
        with Timer(f"Backtest:{ticker}:{chart_period}"):
             # Run 3 variations of the strategy for comparison
             # 1. Standard: Golden Cross (Risky)
             sim_results = run_sma_strategy(chart_df, bench_df=bench_plot_df, investment_size=100000, trend_filter_sma200=False)
             # 2. Safety: Only buy if SMA200 is rising (Conservative)
             sim_safety = run_sma_strategy(chart_df, bench_df=bench_plot_df, investment_size=100000, trend_filter_sma200=True)
             # 3. Strong: Only buy if trend is STRONG (>15% gap) (Aggressive)
             sim_strong = run_sma_strategy(chart_df, bench_df=bench_plot_df, investment_size=100000, trend_filter_sma200=True, min_trend_strength=0.15)

        # Recommendation Badge
        rec_action = "BUY" if sim_safety.get("is_active") else "SELL"
        rec_color = "green" if rec_action == "BUY" else "red"
        
        st.markdown(f"""
            <div style="text-align: right;">
                <span style="background-color: {rec_color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">
                    Recommendation: {rec_action}
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # Render Tabs for Simulation Results
        tab1, tab2, tab3 = st.tabs(["Short Term Trend Buys", "Long Term Safety", "Strong but Safe (>15% Alpha)"])
        
        def render_sim_metrics(sim, rule_desc):
            if not sim or sim.get("trade_count", 0) == 0:
                st.info("No trades executed in this period.")
                return

            sc1, sc2, sc3 = st.columns(3)
            pnl = sim['total_pnl']
            
            # PnL Metric
            with sc1:
                st.metric("Strategy PnL", f"${pnl:,.2f}") 
                if pnl >= 0: st.success(f"{sim['trade_count']} Trades")
                else: st.error(f"{sim['trade_count']} Trades")
                    
            # Compare vs Stock Buy & Hold
            bh_stock = sim.get('bh_stock_pnl', 0.0)
            with sc2:
                diff = bh_stock - pnl 
                st.metric("Buy & Hold (Stock)", f"${bh_stock:,.2f}", delta=f"{diff:+.2f} vs Strat", delta_color="normal")

            # Compare vs Market Buy & Hold
            bh_bench = sim.get('bh_bench_pnl', 0.0)
            with sc3:
                diff_bench = bh_bench - pnl
                st.metric("Buy & Hold (S&P 500)", f"${bh_bench:,.2f}", delta=f"{diff_bench:+.2f} vs Strat", delta_color="normal")
            
            st.caption(f"**Rules:** {rule_desc}.")
            if sim.get('is_active'): st.warning("⚠️ Position Open")
            
            with st.expander("View Trade Log"):
                t_df = pd.DataFrame(sim['trades'])
                if not t_df.empty:
                    st.dataframe(t_df, use_container_width=True)
            st.divider()

        with tab1: render_sim_metrics(sim_results, "Buy \$100k @ Golden Cross, Sell All @ Death Cross")
        with tab2: render_sim_metrics(sim_safety, "Buy $100k @ Golden Cross (IF SMA200 Rising), Sell All @ Death Cross")
        with tab3: render_sim_metrics(sim_strong, "Buy $100k @ Golden Cross (IF SMA200 Rising AND SMA50 > SMA200 + 15%), Sell All @ Death Cross")

        # Log this view to update Recs in system
        if "pressure_score" in dashboard_data:
            strong_rec = "YES" if sim_strong.get("is_active") else "NO"
            try:
                t_tracker = ActivityTracker()
                t_tracker.log_view(ticker, dashboard_data["pressure_score"], recommendation=rec_action, strong_rec=strong_rec)
            except: pass

        # --- SECTION: NEWS FEED ---
        st.markdown("---")
        st.subheader(f"Latest News Headlines ({len(news)})")
        with st.container(height=400):
            for item in news:
                 st.markdown(f"**[{item['title']}]({item['link']})**")
                 st.caption(f"{item['publisher']} • {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d')}")
                 st.write("---")

        # --- SECTION: OPPORTUNITY DISCOVERY (SPIDER MODE) ---
        st.divider()
        st.subheader("🔍 Opportunity Discovery")
        
        rm = RelationshipManager()
        info = rm.get_info(ticker) if ticker else None
        t_fetcher = DataFetcher()
        t_tracker = ActivityTracker()

        # Helper to render competitor cards
        def render_opp_card(symbol, reason, key_suffix):
            try: profile = t_fetcher.get_company_profile(symbol)
            except: profile = {}
            
            rec_state = t_tracker.get_ticker_state(symbol)
            rec = rec_state.get("strategy_rec", "N/A")
            
            name = profile.get('name') or rm.database.get(symbol, {}).get("name", symbol)
            industry = profile.get('industry') or rm.database.get(symbol, {}).get("industry", "Unknown")
            desc = profile.get('summary') or profile.get('description', "No description.")[:150]

            with st.container():
                c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 3, 1])
                c1.markdown(f"**{symbol}**")
                c2.caption(name)
                c3.caption(industry)
                c4.caption(desc)
                if st.button("🔍", key=f"analyze_{symbol}_{key_suffix}"):
                    st.session_state.analysis_ticker = symbol
                    st.rerun()
                st.divider()

        if info:
            t_peers, t_comps, t_graph = st.tabs(["Industry Peers", "Direct Competitors", "Network Graph"])
            
            with t_peers:
                peers = rm.get_industry_peers(ticker)
                for p in peers: render_opp_card(p, "Peer", "peer")
            
            with t_comps:
                comps = rm.get_competitors(ticker)
                if comps:
                    for c in comps: render_opp_card(c, "Competitor", "comp")
                else:
                    st.info("No competitors found in DB.")
                    if st.button(f"🤖 AI: Find Competitors for {ticker}"):
                         with st.spinner("Gemini is researching..."):
                             if rm.expand_knowledge(ticker): st.rerun()
                             else: st.error("Failed to find competitors.")
            
            with t_graph:
                st.caption("Visualizing the competitive landscape.")
                try:
                    dot = "digraph { rankdir=LR; " + f'"{ticker}" [style=filled, fillcolor=lightblue];'
                    l1_comps = rm.get_competitors(ticker)
                    for c1 in l1_comps:
                        dot += f'"{ticker}" -> "{c1}";'
                    dot += "}"
                    st.graphviz_chart(dot)
                except: st.info("Graph viz not supported.")
        else:
             if st.button(f"✨ Expand Knowledge for {ticker}"):
                 with st.spinner("Researching..."):
                     if rm.expand_knowledge(ticker): st.rerun()
