import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.data.ingestion import DataFetcher
from src.analytics.technical import add_technical_features
from src.utils.profiling import Timer
from src.analytics.metrics import calculate_returns, calculate_volatility, calculate_relative_volume, calculate_volume_acceleration

from src.models.forecasting import ForecastModel
from src.analytics.sentiment import SentimentAnalyzer
from src.analytics.fusion import FusionEngine
from src.analytics.gemini_analyst import GeminiAnalyst
import plotly.express as px
from src.analytics.insights import InsightManager
from src.analytics.activity import ActivityTracker
from src.data.relationships import RelationshipManager
from src.utils import defaults
from src.utils import defaults
from src.utils.config import Config

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_technical_features(df):
    """Cached version of technical feature generation. Only re-runs if df changes."""
    return add_technical_features(df)

@st.cache_data(ttl=3600, show_spinner=False)
def load_dashboard_data_v2(ticker: str):
    """
    Consolidated data loader for the stock dashboard.
    Fetches EVERYTHING needed for the view to allow instant interactions.
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
        "metrics": {}
    }

    # 1. Fetch OHLCV (Max)
    df_analysis = fetcher.fetch_ohlcv(ticker, period="max")
    
    if df_analysis.empty:
        return data # Invalid
        
    data["valid"] = True
    
    # 2. Fire-and-forget profile
    if Config.DATA_STRATEGY != "LEGACY":
         try:
             fetcher.get_company_profile(ticker)
         except Exception as e:
             data["profile_error"] = str(e)

    # 3. Technicals (on Max)
    # Re-use existing cached tech function or call directly
    # Since we are inside a cached function, calling another cached function is fine but maybe redundant.
    # Let's call direct to save overhead or use the utility.
    df_analysis = add_technical_features(df_analysis)
    data["df_analysis"] = df_analysis

    # 4. Benchmark (Max)
    bench_df = fetcher.fetch_ohlcv("RSP", period="max")
    if not bench_df.empty:
        bench_df = add_technical_features(bench_df)
        # Align dates
        start_date = df_analysis.index.min()
        bench_df = bench_df[bench_df.index >= start_date]
        data["bench_df"] = bench_df

    # 5. Alt Data & News
    alt_data = fetcher.fetch_alt_data(ticker)
    data["alt_data"] = alt_data
    
    news = fetcher.fetch_news(ticker, limit=100)
    data["news"] = news

    # 6. Analysis / Scores
    # Sentiment
    analyzer = SentimentAnalyzer()
    news_score = analyzer.analyze_news(news)
    data["news_score"] = news_score
    
    # Pressure Score Logic
    fusion = FusionEngine()
    
    # Normalization inputs

    # Pressure Score Logic
    fusion = FusionEngine()
    
    # Normalization inputs
    rsi = df_analysis['rsi'].iloc[-1] if 'rsi' in df_analysis.columns else 50
    from src.analytics.metrics import calculate_trend_strength
    trend_norm = calculate_trend_strength(df_analysis)
    
    # Vols
    returns = calculate_returns(df_analysis['close'])
    vol = calculate_volatility(returns).iloc[-1]
    
    # Vol Norm
    vol_norm = min(1.0, vol * 2) 
    
    # Attention Norm
    cur_att = alt_data['Web_Attention'].iloc[-1]
    att_norm = min(1.0, cur_att / 100.0)

    # Volume Metrics
    rel_vol = calculate_relative_volume(df_analysis, window=20)
    vol_acc = calculate_volume_acceleration(df_analysis, window=3)

    pressure_score = fusion.calculate_pressure_score(
        price_trend=trend_norm,
        volatility_rank=vol_norm,
        sentiment_score=news_score,
        attention_score=att_norm,
        relative_volume=rel_vol,
        volume_acceleration=vol_acc
    )
    data["pressure_score"] = pressure_score
    
    # Save components for UI
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
    
    
    # 7. Peer Benchmarks (Consolidated)
    peers = []
    try:
        rm = RelationshipManager()
        peers = rm.get_industry_peers(ticker, limit=4)
        if not peers:
             peers = [t for t in defaults.DEFAULT_UNIVERSE_TICKERS if t != ticker][:4]
    except Exception as e:
        print(f"RM Error: {e}")
    
    rsi_vals = []
    sent_vals = []
    att_vals = []
    
    # Batch Fetch for performance
    try:
        if peers:
            peer_results = fetcher.fetch_batch_ohlcv(peers, period="6mo")
            
            for p in peers:
                pdf = peer_results.get(p, pd.DataFrame())
                if not pdf.empty:
                    try:
                        pdf = add_technical_features(pdf)
                        if 'rsi' in pdf.columns:
                            rsi_vals.append(pdf['rsi'].iloc[-1])
                    except: pass
    except Exception as e:
        print(f"Peer Batch Error: {e}")

    def safe_avg(vals, default=50):
        return sum(vals) / len(vals) if vals else default

    rsi_avg = safe_avg(rsi_vals, 50)
    sent_avg = safe_avg(sent_vals, 0)
    att_avg = safe_avg(att_vals, 0)
    
    data["benchmarks"] = {
        "rsi_avg": rsi_avg,
        "sent_avg": sent_avg,
        "att_avg": att_avg
    }

    # 8. AI Insights
    # We only FETCH here. We don't want to potentially trigger valid Gemini calls  
    # if we just want to load data. 
    # However, user wants "optimization". If we don't fetch here, 
    # the UI will trigger it and it won't be in this cache.
    # Strategy: 
    # - Try to get Cached Insight.
    # - If None, generate one (this means first load takes time, subsequent are fast).
    # - This satisfies "Consolidated Data Loader".
    
    im = InsightManager()
    
    # Weekly Deep
    cached_weekly = im.get_todays_insight(ticker, report_type="deep_research_weekly", valid_days=7)
    if cached_weekly and ("Rate Limit" in cached_weekly or "Quota" in cached_weekly):
         cached_weekly = None
    data["deep_insight_weekly"] = cached_weekly
    
    # Daily
    cached_daily = im.get_todays_insight(ticker, report_type="deep_dive", valid_days=1)
    if not cached_daily:
        # Generate new if missing
        # NOTE: This makes the first load slower, but ensures 1-hour stability.
        # We need to replicate the generation logic
        analyst = GeminiAnalyst()
        metrics_context = {
            'rsi': rsi,
            'sentiment_score': news_score,
            'attention_score': cur_att,
            'alpha_50': 0, # calculated later or approximate here? market_alpha needs DB
            'pressure_score': pressure_score
        }
        # Try-except to allow data loading even if AI fails
        try:
             report = analyst.analyze_news(ticker, news, metrics_context)
             if "Error" not in report:
                 im.save_insight(ticker, report, report_type="deep_dive")
                 cached_daily = report
        except:
             pass
    
    data["ai_insight"] = cached_daily
    
    
    # 9. Technical Insight (Pattern Recognition)
    # Strategy: Daily Cache (Standard "Technical" Report)
    cached_to_tech = im.get_todays_insight(ticker, report_type="technical")
    if not cached_to_tech:
        try:
             analyst = GeminiAnalyst()
             # Use last 20 periods for patterns
             tech_report = analyst.analyze_technicals(ticker, df_analysis.tail(20))
             if "Error" not in tech_report:
                 im.save_insight(ticker, tech_report, report_type="technical")
                 cached_to_tech = tech_report
        except:
             pass
    data["technical_insight"] = cached_to_tech

    # 10. Tracker Log (Side effect, maybe keep in UI? No, log once per hour load is fine/better)
    # actually logging view should happen when user views it. A cache rebuild might happen in background?
    # Streamlit cache runs only when called. So this is user-driven.
    try:
         tracker = ActivityTracker()
         tracker.log_view(ticker, pressure_score)
    except:
         pass

    return data

def plot_stock_chart(df, ticker, forecast=None, benchmark_df=None):
    # Create figure with secondary y-axis
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, subplot_titles=(f'{ticker} Price vs Market', 'Volume'),
                        row_heights=[0.7, 0.3],
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])

    # Candlestick (Primary Y)
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df['open'],
                                 high=df['high'],
                                 low=df['low'],
                                 close=df['close'],
                                 name='OHLC'), row=1, col=1, secondary_y=False)

    # Forecast
    if forecast is not None:
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat'], line=dict(color='purple', width=2, dash='dash'), name='Forecast'), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_upper'], line=dict(color='rgba(128,0,128,0.2)', width=0), showlegend=False), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_lower'], line=dict(color='rgba(128,0,128,0.2)', width=0), fill='tonexty', fillcolor='rgba(128,0,128,0.2)', name='Confidence'), row=1, col=1, secondary_y=False)

    # MA
    sma20 = df['sma_20'] if 'sma_20' in df.columns else pd.Series([np.nan]*len(df), index=df.index)
    sma50 = df['sma_50'] if 'sma_50' in df.columns else pd.Series([np.nan]*len(df), index=df.index)
    sma200 = df['sma_200'] if 'sma_200' in df.columns else pd.Series([np.nan]*len(df), index=df.index)

    if 'sma_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_20'], line=dict(color='#ffd700', width=1), name='SMA 20'), row=1, col=1, secondary_y=False)
    if 'sma_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_50'], line=dict(color='orange', width=1), name='SMA 50'), row=1, col=1, secondary_y=False)
    if 'sma_200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_200'], line=dict(color='blue', width=1), name='SMA 200'), row=1, col=1, secondary_y=False)

    # --- CROSSOVER LOGIC (Golden/Death Cross) ---
    last_golden_cross_date = None

    def find_crossovers(fast, slow, name):
        nonlocal last_golden_cross_date
        if fast.isna().all() or slow.isna().all(): return
        
        diff = fast - slow
        signs = np.sign(diff)
        sign_change = ((np.roll(signs, 1) - signs) != 0) & (signs != 0)
        sign_change[0] = False
        
        # Get indices
        crossover_dates = df.index[sign_change]
        crossover_vals = slow[sign_change]
        
        if len(crossover_dates) > 0:
            for d, v in zip(crossover_dates, crossover_vals):
                # Check direction
                # If fast > slow now, it was < before -> Golden Cross (Green)
                # We check the value of 'diff' at date 'd'
                is_golden = diff.loc[d] > 0
                
                color = 'green' if is_golden else 'red'
                symbol = 'circle' # filled circle
                label = f"{name} {'Bull' if is_golden else 'Bear'}"
                
                fig.add_trace(go.Scatter(
                    x=[d], y=[v],
                    mode='markers',
                    marker=dict(symbol=symbol, size=14, color=color, line=dict(color='white', width=1)),
                    name=label,
                    showlegend=False, # Too many items if we legend every point
                    hoverinfo='text',
                    hovertext=f"{d.date()} | {label}"
                ), row=1, col=1, secondary_y=False)
                
                if name == "SMA20/50" and is_golden:
                    if last_golden_cross_date is None or d > last_golden_cross_date:
                        last_golden_cross_date = d

        # Add a dummy trace for legend explanation if potential crosses exist
        if len(crossover_dates) > 0:
             fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', 
                                    marker=dict(symbol='circle', size=10, color='green'), 
                                    name=f'{name} Golden Cross', legendgroup=f'{name}_bull'), row=1, col=1)
             fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', 
                                    marker=dict(symbol='circle', size=10, color='red'), 
                                    name=f'{name} Death Cross', legendgroup=f'{name}_bear'), row=1, col=1)


    # 1. SMA 20 vs SMA 50 (Short Term Momentum)
    find_crossovers(sma20, sma50, "Signal")
    
    # 2. SMA 50 vs SMA 200 (Major Trend)
    # find_crossovers(sma50, sma200, "Trend") # Optional: Keep simple or add both
    # User specifically asked for SMA20/50 buy/sell signals.
    # Let's do both but maybe different markers? Or just same/similar.
    # User prompt: "when the SMA20 cross the SMA50... circle green/red"
    # User also asked for "where SMA50 crosses SMA200" with different color.
    # Let's keep 50/200 distinct -> Purple/Orange? 
    # Actually, let's treat 50/200 as Major Signals.
    
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

    find_major_crossovers(sma50, sma200, "Major Trend (50/200)")

    # --------------------------------------------

    # Benchmark (Primary Y for visibility/comparison)
    if benchmark_df is not None and 'sma_200' in benchmark_df.columns:
        # Plot directly, let Plotly handle date alignment on shared X axis
        fig.add_trace(go.Scatter(x=benchmark_df.index, y=benchmark_df['sma_200'], 
                               line=dict(color='#9370DB', width=3), # Medium Purple
                               name='S&P Market Trend (Indexed)'), 
                      row=1, col=1, secondary_y=False)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="Price & S&P (RSP)", secondary_y=False, row=1, col=1)
    
    return fig, last_golden_cross_date



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
        # Ticker Input
        c_tick, c_like = st.columns([3, 1])
        with c_tick:
            ticker = st.text_input("Ticker Symbol", value=st.session_state.analysis_ticker).upper().strip()
        
        with c_like:
            st.text(" ")
            st.text(" ")
            # Like button
            tracker = ActivityTracker()
            is_liked = tracker.is_liked(ticker)
            label = "❤️" if is_liked else "🤍"
            if st.button(label, key="like_btn", use_container_width=True):
                tracker.toggle_like(ticker)
                st.rerun()
        # Update session state if manual change
        if ticker != st.session_state.analysis_ticker:
            st.session_state.analysis_ticker = ticker
            
        # Update session state if manual change
        if ticker != st.session_state.analysis_ticker:
            st.session_state.analysis_ticker = ticker
            
        show_forecast = st.checkbox("Show Forecast (30d)", value=False)

        # --- Add to Portfolio Widget ---
        if 'portfolio_manager' in st.session_state:
            pm = st.session_state.portfolio_manager
            portfolios = pm.list_portfolios()
            
            if portfolios:
                with st.expander("📂 Add to Portfolio"):
                    # Select Portfolio
                    p_names = [p.name for p in portfolios]
                    selected_p_name = st.selectbox("Select Portfolio", p_names)
                    selected_p = next((p for p in portfolios if p.name == selected_p_name), None)
                    
                    # Inputs
                    c_shares, c_price = st.columns(2)
                    with c_shares:
                        shares = st.number_input("Shares", min_value=1, value=10)
                    with c_price:
                        # Try to guess price if data loaded, else 0
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
        alpha_banner = st.empty()
        
        # --- NEW: Consolidated Data Load ---
        # This blocks on first run, then is instant for 1 hour.
        with st.spinner(f"⚡ Loading Dashboard for {ticker}..."):
            dashboard_data = load_dashboard_data_v2(ticker)
            
        if not dashboard_data["valid"]:
             st.error(f"No data found for ticker '{ticker}'. Please ensure valid ticker, internet connection, or try again.")
             return

        # Unpack Data
        if dashboard_data.get("ai_insight") and "valid" in dashboard_data and dashboard_data["valid"]:
             st.toast("✅ AI Insight Loaded from Cache (Fast Mode)", icon="⚡")
        elif not dashboard_data.get("valid"):
             st.toast("❌ Data Load Failed")
        else:
             st.toast("⚠️ AI Insight Generated (Cache Miss)", icon="🤖")

        df_analysis = dashboard_data["df_analysis"]
        bench_df = dashboard_data["bench_df"]
        alt_data = dashboard_data["alt_data"]
        news = dashboard_data["news"]
        pressure_score = dashboard_data["pressure_score"]
        news_score = dashboard_data["news_score"]
        comps = dashboard_data["components"]
        
        # Production Check
        if Config.DATA_STRATEGY == "PRODUCTION":
             is_syn = df_analysis['source'] != 'live' if 'source' in df_analysis.columns else pd.Series([True] * len(df_analysis), index=df_analysis.index)
             syn_count = is_syn.sum()
             if syn_count > 0:
                 pct = (syn_count / len(df_analysis)) * 100
                 st.warning(f"⚠️ **Production Mode**: {pct:.1f}% of loaded history is Synthetic. Metrics may be approximate.")
             elif df_analysis.attrs.get("source") == "🟢 LIVE":
                 st.info("✨ **Day 1 Analysis**: Fresh historic data retrieved. Tracking initiatied for forward testing.")

        source_tag = df_analysis.attrs.get("source", "⚪ UNKNOWN")
        st.caption(f"Data Source: {source_tag}")

        # Forecast (using analysis df)
        forecast_df = None
        if show_forecast:
            with st.spinner("Generating forecast..."):
                model = ForecastModel()
                forecast_df = model.train_predict(df_analysis)
        
        # Metrics (Latest)
        returns = calculate_returns(df_analysis['close'])
        vol = comps["vol"]
        last_price = df_analysis['close'].iloc[-1]
        prev_price = df_analysis['close'].iloc[-2]
        change = (last_price - prev_price) / prev_price
        
        # Display Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Price", f"${last_price:.2f}", f"{change:.2%}")
        m2.metric("Volatility (Ann.)", f"{vol:.2%}")
        m3.metric("Volume", f"{df_analysis['volume'].iloc[-1]:,}")

        # --- PRE-CALCULATE SIGNALS (Components unpacked above) ---
        # Re-construct some locals for UI logic
        vol_acc = comps["vol_acc"]
        rel_vol = comps["rel_vol"]
        att_norm = comps["att_norm"]
        cur_att = comps["cur_att"]
        rsi = comps["rsi"]

        # --- SECTION 1: MARKET PRESSURE (HERO) & MULTI-MODAL ANALYSIS ---
        st.divider()
        st.subheader("Multi-Modal Analysis")

        # 1. Pressure Score Display (Prominent)
        tp_col1, tp_col2 = st.columns([1, 2])
        with tp_col1:
            st.metric(
                "Pressure Score", 
                f"{pressure_score:.1f}/100",
                help="""
                **Market Pressure Score (Hybrid)**
                A composite index tracking:
                1. Price Trend
                2. Sentiment
                3. Retail Interest (Social + Volume Anomalies)
                4. Volatility
                """
            )
            st.progress(pressure_score / 100)
            
            # Dynamic Label for Retail Signal
            retail_msg = ""
            if vol_acc > 0.05:
                retail_msg = "🚀 Volume Accelerating!"
            elif rel_vol > 1.2:
                retail_msg = "🔥 High Volume Anomaly"
            elif att_norm > 0.2:
                retail_msg = "🗣️ High Social Chatter"
            
            if retail_msg:
                st.caption(f"{retail_msg}")

            st.info(f"""
            **Interpretation:**
            - **> 75 (Bullish):** High buying pressure.
            - **< 25 (Bearish):** High selling pressure.
            """)

        with tp_col2:
             # Plot Alt Data (Moved from Tab 2)
            fig_alt = make_subplots(specs=[[{"secondary_y": True}]])
            fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Web_Attention'], name="Web Attention"), secondary_y=False)
            fig_alt.add_trace(go.Scatter(x=alt_data.index, y=alt_data['Social_Sentiment'], name="Social Sentiment", line=dict(dash='dot')), secondary_y=True)
            fig_alt.update_layout(title="Alternative Data Signals (30d)", height=250, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_alt, use_container_width=True)

        # 2. Components Breakdown (Moved from Tab 2)
        st.write("#### Signal Components")
        
        # --- CALC BENCHMARKS (Cached) ---
        benchmarks = dashboard_data.get("benchmarks", {"rsi_avg": 50, "sent_avg": 0, "att_avg": 0})
        rsi_avg = benchmarks["rsi_avg"]
        
        # --- DEFINITIONS RESTORED ---
        att_delta = cur_att - benchmarks["att_avg"]
        rsi_delta = rsi - rsi_avg
        # ----------------------------

        st.markdown("---")
        st.subheader("First-Class AI Insight")
        st.caption("Qualitative Analysis of Multi-Modal Signals")
        
        im = InsightManager() 
        # 1. Check for Weekly Deep Research (Cached in dashboard_data)
        cached_weekly = dashboard_data["deep_insight_weekly"]

        if cached_weekly:
             st.info(f"🧬 **Deep Research Report** (Cached < 7 days)")
             st.markdown(cached_weekly)
        
        else:
            # 2. Standard Daily Insight (Cached in dashboard_data)
            cached_daily = dashboard_data["ai_insight"]
            
            if cached_daily:
                st.success(f"Standard Analysis from {datetime.now().strftime('%Y-%m-%d')} (Cached)")
                st.markdown(cached_daily)
            else:
                 # This path should mostly be covered by the cache loader now,
                 # but if cache loader failed to gen, we offer button.
                # Generate Standard
                if st.button("Generate AI Insight"):
                    with st.spinner("Gemini is connecting the dots..."):
                        analyst = GeminiAnalyst()
                        metrics_context = {
                            'rsi': rsi,
                            'sentiment_score': news_score,
                            'attention_score': cur_att,
                            'alpha_50': g50_a if 'g50_a' in locals() else 0,
                            'pressure_score': pressure_score
                        }
                        report = analyst.analyze_news(ticker, news, metrics_context)
                        
                        if "Error" not in report:
                            im.save_insight(ticker, report, report_type="deep_dive")
                            st.rerun()
                        else:
                            st.error(report)

            # 3. Deep Research Upgrade Option
            st.write("#### 🧬 Need Deeper Answers?")
            
            # Safe Alpha Check
            from src.analytics.market_comparison import calculate_market_alpha
            market_alpha = calculate_market_alpha(ticker)
            
            st.caption(f"Unlock implied mixed signals or verify why {ticker} is {'beating' if market_alpha > 0 else 'trailing'} the market.")
            
            if st.button("Run Deep Research (Gemini 1.5 Pro)"):
                 with st.spinner("🕵️‍♂️ Conducting Deep Research (Industry, Competitors, Future)... This may take 30-60s."):
                    analyst = GeminiAnalyst()
                    metrics_context = {
                        'rsi': rsi,
                        'sentiment_score': news_score,
                        'attention_score': cur_att,
                        'alpha_50': market_alpha,
                        'pressure_score': pressure_score
                    }
                    # Use new method
                    deep_report = analyst.perform_deep_research(ticker, news, metrics_context)
                    
                    if "Error" not in deep_report and "Rate Limit" not in deep_report:
                        im.save_insight(ticker, deep_report, report_type="deep_research_weekly")
                        st.rerun()
                    else:
                        st.error(deep_report)
        
        # --- DAILY AI TECHNICAL ANALYSIS (Existing) ---
        st.markdown("---")
        st.write("#### 🤖 Daily Technical Summary")
        
        cached_insight = dashboard_data.get("technical_insight")
        
        if cached_insight:
            st.success(f"Analysis from {datetime.now().strftime('%Y-%m-%d')} (Cached)")
            st.markdown(cached_insight)
        else:
            # Fallback if cache failed to generate (e.g. rate limit during load)
            if st.button("Generate Technical Analysis"):
                 with st.spinner("Analyzing chart patterns..."):
                    analyst = GeminiAnalyst()
                    # Use analysis df for pattern recognition
                    tech_report = analyst.analyze_technicals(ticker, df_analysis.tail(20))
                    if "Error" not in tech_report:
                        im.save_insight(ticker, tech_report, report_type="technical")
                        st.markdown(tech_report)
                    else:
                        st.error(tech_report)

        # --- SECTION 2: PRICE & TECHNICALS (Was Tab 1) ---
        st.divider()
        st.header("Price & Technicals")
        
        # Chart Timeframe Selector
        chart_period = st.radio("Timeframe", 
                              options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                              index=3, # Default 1y
                              horizontal=True,
                              key="chart_period_selector")
                              
        # Fetch Data for Chart (Decoupled from Signal Analysis)
        # Fetch Benchmark Once (Max) if not already
        # (We could move this top-level, but lazy loading here is okay if we use local slicing)
        # Actually, to avoid re-fetch on radio change, we rely on st.cache logic or move it up.
        # But render_stock_view runs entirely on radio change. 
        # So if we fetched 'max' above (df_analysis), we just slice it here.
        
        # Helper to slice DataFrame based on period string
        def slice_period(df, period):
            if df.empty or period == "max": return df
            
            # Approximate slicing
            days_map = {
                "1mo": 30, "3mo": 90, "6mo": 180, 
                "1y": 365, "2y": 730, "5y": 1825
            }
            days = days_map.get(period, 365)
            start_date = df.index.max() - pd.Timedelta(days=days)
            return df[df.index >= start_date]

        # Slice for Chart
        chart_df = slice_period(df_analysis, chart_period)
        
        # Fetch Benchmark (RSP) - We can also fetch this 'max' once
        # Since we don't store bench_df in session, we fetch it 'max' here.
        # Ideally fetcher caches this.
        # with st.spinner("Loading Market Context..."):
        #      bench_df = fetcher.fetch_ohlcv("RSP", period="max")
        #      if not bench_df.empty:
        #          bench_df = add_technical_features(bench_df)
        #          # Slice to match chart range
        #          if not chart_df.empty:
        #              start_date = chart_df.index.min()
        #              bench_df = bench_df[bench_df.index >= start_date]
        
        # USING PRE-FETCHED BENCHMARK
        bench_plot_df = pd.DataFrame()
        if not bench_df.empty:
             if not chart_df.empty:
                 start_date = chart_df.index.min()
                 bench_plot_df = bench_df[bench_df.index >= start_date].copy()
                    
        if not chart_df.empty:
            # --- Growth Index Calculation ---
            st.write("") # Spacer
            
            def get_growth_metrics(stock_df, market_df, col_name):
                s_growth = 0.0
                m_growth = 0.0
                alp = 0.0
                s_start_val = 0.0
                f_valid_date = None
                
                # 1. Stock SMA Growth
                if col_name in stock_df.columns:
                    valid_s = stock_df[col_name].dropna()
                    if not valid_s.empty:
                        f_valid_date = valid_s.index[0]
                        s_start_val = valid_s.iloc[0]
                        s_end_val = valid_s.iloc[-1]
                        if s_start_val > 0:
                            s_growth = (s_end_val - s_start_val) / s_start_val
                
                # 2. Market SMA Growth (Aligned)
                if not market_df.empty and col_name in market_df.columns and f_valid_date:
                    bslice = market_df[market_df.index >= f_valid_date]
                    valid_b = bslice[col_name].dropna()
                    if not valid_b.empty:
                        b_start = valid_b.iloc[0]
                        b_end = valid_b.iloc[-1]
                        if b_start > 0:
                            m_growth = (b_end - b_start) / b_start
                            
                alp = s_growth - m_growth
                return s_growth, m_growth, alp, s_start_val, f_valid_date

            # Calculate Metrics
            g50_s, g50_m, g50_a, start_50, date_50 = get_growth_metrics(chart_df, bench_plot_df, 'sma_50')
            g200_s, g200_m, g200_a, start_200, date_200 = get_growth_metrics(chart_df, bench_plot_df, 'sma_200')
            
            # Display Section 1: Medium Term (SMA50)
            # Only show if SMA50 data exists (some stocks/IPOs might not have it)
            if start_50 > 0:
                c1, c2, c3 = st.columns(3)
                c1.metric(f"{ticker} SMA50 Trend", f"{g50_s:+.2%}", help="Medium-term trend growth (50-day MA).")
                c2.metric("S&P 500 SMA50 Trend", f"{g50_m:+.2%}")
                c3.metric("Alpha (SMA50)", f"{g50_a:+.2%}", delta_color="normal" if g50_a >= 0 else "inverse")
                
                if g50_a > 0:
                    alpha_banner.success(f"🚀 {ticker} is beating the market! (Positive SMA50 Alpha)")
                else:
                    alpha_banner.empty()
            
            # Display Section 2: Long Term (SMA200)
            if start_200 > 0:
                d1, d2, d3 = st.columns(3)
                d1.metric(f"{ticker} SMA200 Trend", f"{g200_s:+.2%}", help="Long-term trend growth (200-day MA).")
                d2.metric("S&P 500 SMA200 Trend", f"{g200_m:+.2%}")
                # Prepare Plot Data (Benchmark Normalization)
            bench_plot_df = pd.DataFrame() # fallback
            if not bench_df.empty:
                # Filter benchmark to match stock date range
                bench_plot_df = bench_df[bench_df.index.isin(chart_df.index)].copy()
                if not bench_plot_df.empty and 'sma_200' in bench_plot_df.columns:
                    # Normalize bench SMA200 to start at same price as stock (visual comparison)
                    s_start = start_200 # Stock SMA200 start price
                    b_start = bench_plot_df['sma_200'].iloc[0]
                    if b_start > 0 and s_start > 0:
                        ratio = s_start / b_start
                        bench_plot_df['sma_200'] = bench_plot_df['sma_200'] * ratio
            
            if start_200 > 0:
                st.caption(f"ℹ️ The **S&P 500 Trend** line is visually scaled to start at {ticker}'s price (${start_200:.2f}) to make the growth comparison easy.")

            fig, last_cross_date = plot_stock_chart(chart_df, ticker, forecast_df, benchmark_df=bench_plot_df)
                
            # Display Last Golden Cross
            if last_cross_date:
                st.info(f"✨ **Last Golden Cross (SMA20 > SMA50)**: {last_cross_date.strftime('%Y-%m-%d')}")
            
            st.plotly_chart(fig, key=f"chart_{ticker}_{chart_period}")
            with st.expander(f"Raw Data ({chart_period})"):
                st.dataframe(chart_df.tail(10))
        else:
            st.error("No chart data available for this period.")
            
            # --- News Feed (Moved here for context) ---
            # Keeping News below charts or with Multi-Modal?
            # User said "Multi-Modal Analysis ... sit above Price".
            # News fits with Multi-Modal. But let's put it below charts as "Latest Info" 
            # OR put it back in Multi-Modal section.
            # I will put it at the very bottom of the Multi-Modal section (before charts).
            
            # (Insert News Feed back up?)
            # Actually, let's keep it simple. Let's put News at the bottom of the page or in a sidebar?
            # User didn't specify. I'll leave it out of the main flow for now or put it at the end.
            
            st.markdown("---")
            st.subheader(f"Latest News Headlines ({len(news)})")
            st.caption("Expanded coverage for AI contexts.")
            
            with st.container(height=400):
                for item in news:
                     st.markdown(f"**[{item['title']}]({item['link']})**")
                     st.caption(f"{item['publisher']} • {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d')}")
                     st.write("---")

            # --- Manage Portfolio Positions ---
            st.write("---")
            st.subheader("Manage Portfolio Positions")
            
            if 'portfolio_manager' in st.session_state:
                pm = st.session_state.portfolio_manager
                portfolios = [p for p in pm.list_portfolios() if p.status.value != "Archived"]
                
                if not portfolios:
                    st.caption("No active portfolios found.")
                
                for p in portfolios:
                    with st.container():
                        st.markdown(f"**{p.name}**")
                        current_qty = p.holdings.get(ticker, 0)
                        
                        if current_qty > 0:
                            # HELD
                            c_hold1, c_hold2 = st.columns([1, 2])
                            with c_hold1:
                                st.info(f"Held: {current_qty} shares")
                            with c_hold2:
                                if st.button(f"Remove/Sell All ({p.name})", key=f"rm_{p.id}_{ticker}"):
                                    p.remove_ticker(ticker, last_price)
                                    st.toast(f"Sold all named {ticker} from {p.name}")
                                    st.rerun()
                        
                        st.caption(f"{'Increase' if current_qty > 0 else 'Add'} Position in {p.name}")
                        cols = st.columns([1, 1, 1])
                        with cols[0]:
                            shares_add = st.number_input("Shares", min_value=1, value=10, key=f"sh_{p.id}_{ticker}")
                        with cols[1]:
                            cost_add = st.number_input("Price", value=float(last_price), key=f"pr_{p.id}_{ticker}")
                        with cols[2]:
                            btn_label = "Add" if current_qty == 0 else "Increase"
                            if st.button(btn_label, key=f"add_{p.id}_{ticker}"):
                                try:
                                    p.update_holdings(ticker, shares_add, cost_add)
                                    st.toast(f"Added {shares_add} {ticker} to {p.name}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        st.divider()



    # --- Opportunity Discovery (Added) ---
    st.divider()
    st.subheader("🔍 Opportunity Discovery")
    
    # Get peers and competitors
    rm = RelationshipManager()
    info = rm.get_info(ticker) if ticker else None
    
    def render_opp_card(symbol, reason, key_suffix):
        with st.container():
            col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
            with col_r1:
                st.markdown(f"**{symbol}**")
                nm = rm.database.get(symbol, {}).get("name", symbol)
                st.caption(nm)
            with col_r2:
                st.caption(reason)
            with col_r3:
                if st.button("🔍", key=f"analyze_opp_{symbol}_{key_suffix}", help=f"Analyze {symbol}"):
                    st.session_state.analysis_ticker = symbol
                    st.rerun()
            st.divider()

    if info:
        t_peers, t_comps = st.tabs(["Industry Peers", "Direct Competitors"])
        
        with t_peers:
            peers = rm.get_industry_peers(ticker)
            if peers:
                for p in peers:
                    render_opp_card(p, f"Peer in {info.get('industry')}", "peer")
            else:
                st.info("No industry peers found.")
        
        with t_comps:
            comps = rm.get_competitors(ticker)
            if comps:
                for c in comps:
                    render_opp_card(c, f"Competitor of {ticker}", "comp")
            else:
                st.info("No direct competitors listed.")
                if st.button(f"🤖 AI: Find Competitors for {ticker}", key=f"ai_find_comp_{ticker}"):
                     with st.spinner("Gemini is researching competitors..."):
                         if rm.expand_knowledge(ticker):
                             st.success("Competitors found!")
                             st.rerun()
                         else:
                             st.error("Failed to find competitors. Usage Limit Exceeded (Daily Quota) or Invalid API Key.")
    else:
         if ticker:
             col_miss1, col_miss2 = st.columns([3, 1])
             with col_miss1:
                 st.info(f"No relationship data found for {ticker}.")
             with col_miss2:
                 if st.button(f"✨ Expand Knowledge", key=f"ai_exp_stock_{ticker}"):
                     with st.spinner(" researching..."):
                         if rm.expand_knowledge(ticker):
                             st.rerun()
