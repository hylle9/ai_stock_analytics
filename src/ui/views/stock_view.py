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
from src.analytics.insights import InsightManager
from src.analytics.activity import ActivityTracker
from src.data.relationships import RelationshipManager
from src.utils import defaults

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
    if 'sma_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_50'], line=dict(color='orange', width=1), name='SMA 50'), row=1, col=1, secondary_y=False)
    if 'sma_200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['sma_200'], line=dict(color='blue', width=1), name='SMA 200'), row=1, col=1, secondary_y=False)

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
    # fig.update_yaxes(title_text="S&P Index (RSP)", secondary_y=True, showgrid=False, autorange=True, row=1, col=1)
    
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
        # Ticker Input
        c_tick, c_like = st.columns([3, 1])
        with c_tick:
            ticker = st.text_input("Ticker Symbol", value=st.session_state.analysis_ticker).upper()
        
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
        # 1. Fetch Analysis Data (Fixed 2y for stable signals)
        df_analysis = fetcher.fetch_ohlcv(ticker, period="2y")
        
        if not df_analysis.empty:
            # Add features for Analysis
            df_analysis = add_technical_features(df_analysis)
            
            # Forecast (using analysis df)
            forecast_df = None
            if show_forecast:
                with st.spinner("Generating forecast..."):
                    model = ForecastModel()
                    forecast_df = model.train_predict(df_analysis)
            
            # Metrics (Latest)
            returns = calculate_returns(df_analysis['close'])
            vol = calculate_volatility(returns).iloc[-1]
            last_price = df_analysis['close'].iloc[-1]
            prev_price = df_analysis['close'].iloc[-2]
            change = (last_price - prev_price) / prev_price
            
            # Display Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Price", f"${last_price:.2f}", f"{change:.2%}")
            m2.metric("Volatility (Ann.)", f"{vol:.2%}")
            m3.metric("Volume", f"{df_analysis['volume'].iloc[-1]:,}")

            # --- PRE-CALCULATE SIGNALS ---
            # Fetch Alt Data
            alt_data = fetcher.fetch_alt_data(ticker)
            # Fetch Expanded News (100 items for deeper AI analysis)
            news = fetcher.fetch_news(ticker, limit=100)

            # Analyze Sentiment
            analyzer = SentimentAnalyzer()
            news_score = analyzer.analyze_news(news)

            # Calculate Pressure Score
            fusion = FusionEngine()
            im = InsightManager()  # Instantiate here to be available for both Deep Dive and Technical Summary

            # Normalize inputs for fusion (simplified)
            # Trend: RSI > 50 is positive
            rsi = df_analysis['rsi'].iloc[-1] if 'rsi' in df_analysis.columns else 50
            trend_norm = (rsi - 50) / 50 # -1 to 1

            # Volatility: normalized against history (simplified)
            vol_norm = min(1.0, vol * 2) # Cap at 50% vol

            # Attention: normalized 0 to 1
            att_norm = alt_data['Web_Attention'].iloc[-1] / 100

            pressure_score = fusion.calculate_pressure_score(
                price_trend=trend_norm,
                volatility_rank=vol_norm,
                sentiment_score=news_score,
                attention_score=att_norm
            )

            # --- LOG ACTIVITY ---
            try:
                tracker = ActivityTracker()
                tracker.log_view(ticker, pressure_score)
            except Exception as e:
                print(f"Error logging activity: {e}")

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
                    **Market Pressure Score**
                    A composite index reflecting the aggregate buy/sell pressure on the asset.
                    """
                )
                st.progress(pressure_score / 100)
                
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
            
            # --- CALC BENCHMARKS START ---
            rm = RelationshipManager()
            peers = rm.get_industry_peers(ticker, limit=4)
            if not peers:
                # Fallback to default universe if no peers found
                peers = [t for t in defaults.DEFAULT_UNIVERSE_TICKERS if t != ticker][:4]
            
            rsi_vals = []
            sent_vals = []
            att_vals = []
            
            # Quick fetch for peers
            for p in peers:
                # Technicals
                pdf = fetcher.fetch_ohlcv(p, period="6mo")
                if not pdf.empty:
                    pdf = add_technical_features(pdf)
                    if 'rsi' in pdf.columns:
                        rsi_vals.append(pdf['rsi'].iloc[-1])
                
                # Alt Data
                adf = fetcher.fetch_alt_data(p, days=1)
                if not adf.empty:
                    att_vals.append(adf['Web_Attention'].iloc[-1])
                    sent_vals.append(adf['Social_Sentiment'].iloc[-1])
            
            def safe_avg(vals, default=50):
                return sum(vals) / len(vals) if vals else default

            rsi_avg = safe_avg(rsi_vals, 50)
            sent_avg = safe_avg(sent_vals, 0)
            att_avg = safe_avg(att_vals, 0)
            
            # --- DEFINITIONS RESTORED ---
            cur_att = alt_data['Web_Attention'].iloc[-1]
            att_delta = cur_att - att_avg
            rsi_delta = rsi - rsi_avg
            # ----------------------------
            
            # --- CALC BENCHMARKS END ---

            st.markdown("---")
            st.subheader("First-Class AI Insight")
            st.caption("Qualitative Analysis of Multi-Modal Signals")
            
            # 1. Check for Weekly Deep Research (Highest Priority)
            # Use valid_days=7 for weekly cache
            cached_weekly = im.get_todays_insight(ticker, report_type="deep_research_weekly", valid_days=7)
            
            # Invalid Cache Check (Don't show error messages as cached reports)
            if cached_weekly and ("Rate Limit" in cached_weekly or "Quota" in cached_weekly):
                cached_weekly = None
            
            if cached_weekly:
                 st.info(f"🧬 **Deep Research Report** (Cached < 7 days)")
                 st.markdown(cached_weekly)
            
            else:
                # 2. Standard Daily Insight (Fallback)
                cached_daily = im.get_todays_insight(ticker, report_type="deep_dive", valid_days=1)
                
                if cached_daily:
                    st.success(f"Standard Analysis from {datetime.now().strftime('%Y-%m-%d')} (Cached)")
                    st.markdown(cached_daily)
                else:
                    # Generate Standard
                    if st.button("Generate AI Insight"):
                        with st.spinner("Gemini is connecting the dots..."):
                            analyst = GeminiAnalyst()
                            metrics_context = {
                                'rsi': rsi,
                                'sentiment_score': news_score,
                                'attention_score': cur_att,
                                'alpha_50': g50_a if 'g50_a' in locals() else 0,
                                'pressure_score': score if 'score' in locals() else 50
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
                            'pressure_score': score if 'score' in locals() else 50
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
            
            cached_insight = im.get_todays_insight(ticker)
            
            if cached_insight:
                st.success(f"Analysis from {datetime.now().strftime('%Y-%m-%d')} (Cached)")
                st.markdown(cached_insight)
            else:
                with st.spinner("Analyzing chart patterns..."):
                    analyst = GeminiAnalyst()
                    # Use analysis df for pattern recognition
                    tech_report = analyst.analyze_technicals(ticker, df_analysis.tail(20))
                    if "Error" not in tech_report:
                        im.save_insight(ticker, tech_report)
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
            if chart_period == "2y":
                chart_df = df_analysis # reuse
            else:
                chart_df = fetcher.fetch_ohlcv(ticker, period=chart_period)
                if not chart_df.empty:
                    chart_df = add_technical_features(chart_df)
            
            # Fetch Benchmark (RSP - Equal Weight S&P 500)
            with st.spinner("Loading Market Context..."):
                bench_df = fetcher.fetch_ohlcv("RSP", period="max")
                if not bench_df.empty:
                    bench_df = add_technical_features(bench_df)
                    # Slice to match chart timeframe (prevents rendering issues with 20y history)
                    if not chart_df.empty:
                        start_date = chart_df.index.min()
                        bench_df = bench_df[bench_df.index >= start_date]
                        
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
                g50_s, g50_m, g50_a, start_50, date_50 = get_growth_metrics(chart_df, bench_df, 'sma_50')
                g200_s, g200_m, g200_a, start_200, date_200 = get_growth_metrics(chart_df, bench_df, 'sma_200')
                
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
                    d3.metric("Alpha (SMA200)", f"{g200_a:+.2%}", delta_color="normal" if g200_a >= 0 else "inverse")

                # Rebase Benchmark (Using SMA 200 values for the visual line)
                bench_plot_df = bench_df.copy()
                if g200_s != 0 and g200_m != 0 and date_200:
                     try:
                         b_align_val = bench_df.loc[bench_df.index >= date_200]['sma_200'].iloc[0]
                         scale_factor = start_200 / b_align_val
                         bench_plot_df['sma_200'] = bench_plot_df['sma_200'] * scale_factor
                     except (IndexError, KeyError):
                         pass
                
                if start_200 > 0:
                    st.caption(f"ℹ️ The **S&P 500 Trend** line is visually scaled to start at {ticker}'s price (${start_200:.2f}) to make the growth comparison easy.")

                st.plotly_chart(plot_stock_chart(chart_df, ticker, forecast_df, benchmark_df=bench_plot_df), use_container_width=True)
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

        else:
            st.error(f"No data found for ticker '{ticker}'.")
            return

    # --- Opportunity Discovery (Added) ---
    st.divider()
    st.subheader("🔍 Opportunity Discovery")
    
    # Get peers and competitors
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
                             st.error("Failed to find competitors. Check API Key.")
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
