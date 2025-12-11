import streamlit as st
import pandas as pd
from src.data.universe import UniverseManager, Universe
from src.data.ingestion import DataFetcher
from src.analytics.backtester import run_sma_strategy

def render_universe_view():
    st.header("Universe Management")
    
    manager = UniverseManager()
    universes = manager.list_universes()
    
    # Sidebar for selection using session state for control
    if "universe_action" not in st.session_state:
        st.session_state.universe_action = "Manage Existing"
        
    action = st.sidebar.radio("Action", ["Manage Existing", "Create New"], key="universe_action")

    if action == "Create New":
        st.subheader("Create New Universe")
        
        # Check limit early
        if len(universes) >= 10:
            st.error(f"Universe limit reached ({len(universes)}/10). Please delete an existing universe first.")
        else:
            with st.form("create_universe_form"):
                new_name = st.text_input("Universe Name")
                new_description = st.text_area("Description")
                new_tickers = st.text_area("Tickers (comma separated)", "AAPL, MSFT, GOOGL")
                
                if st.form_submit_button("Create"):
                    if new_name:
                        if new_name in universes:
                            st.error("Universe with this name already exists.")
                        else:
                            tickers_list = [t.strip().upper() for t in new_tickers.split(",") if t.strip()]
                            u = Universe(new_name, tickers_list, new_description)
                            try:
                                manager.save_universe(u)
                                st.success(f"Universe '{new_name}' created!")
                                # Switch to manage view
                                st.session_state.universe_action = "Manage Existing"
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.error("Name is required")

    elif action == "Manage Existing":
        if not universes:
            st.info("No universes found. Create one to get started.")
            return

        selected_universe_name = st.sidebar.selectbox("Select Universe", universes)
        
        if selected_universe_name:
            u = manager.load_universe(selected_universe_name)
            if u:
                # Header showing details
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(f"🌌 {u.name}")
                    st.caption(u.description)
                with c2:
                    st.metric("Tickers", len(u.tickers))
                
                # --- STRATEGY ANALYSIS ---
                st.divider()
                st.subheader("Accumulated Yearly Strategy Gains")
                st.caption("Simulate performance of all stocks in this universe over the last 1 year.")
                
                if st.button("RUN ANALYSIS 🚀", type="primary"):
                    fetcher = DataFetcher()
                    
                    # Fetch Benchmark (S&P 500 Equal Weight or SPY)
                    with st.spinner("Fetching Market Data..."):
                        bench_df = fetcher.fetch_ohlcv("RSP", period="1y")
                    
                    # Accumulators
                    total_strat1_pnl = 0.0 # Short Term
                    total_strat2_pnl = 0.0 # Long Term Safety
                    total_strat3_pnl = 0.0 # Strong but Safe
                    total_bh_bench_pnl = 0.0 # Buy & Hold S&P500
                    
                    investment_per_stock = 100000.0
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    results_log = []
                    
                    for i, ticker in enumerate(u.tickers):
                        status_text.text(f"Analyzing {ticker}...")
                        progress_bar.progress((i + 1) / len(u.tickers))
                        
                        try:
                            # 1. Fetch Data (1y)
                            df = fetcher.fetch_ohlcv(ticker, period="1y")
                            
                            if not df.empty and len(df) > 50:
                                # Ensure Analysis Columns Exist
                                if 'sma_20' not in df.columns:
                                    df['sma_20'] = df['close'].rolling(window=20).mean()
                                    df['sma_50'] = df['close'].rolling(window=50).mean()
                                    df['sma_200'] = df['close'].rolling(window=200).mean()
                                
                                # Align Benchmark
                                sim_bench_df = pd.DataFrame()
                                if not bench_df.empty:
                                    sim_bench_df = bench_df[bench_df.index.isin(df.index)]

                                # 2. Run Strategies (Matching Stock View)
                                
                                # #1 "Short Term Trend Buys" (Standard)
                                sim_1 = run_sma_strategy(
                                    df, bench_df=sim_bench_df,
                                    investment_size=investment_per_stock, 
                                    trend_filter_sma200=False
                                )
                                
                                # #2 "Long Term Safety" (Filtered)
                                sim_2 = run_sma_strategy(
                                    df, bench_df=sim_bench_df,
                                    investment_size=investment_per_stock, 
                                    trend_filter_sma200=True
                                )
                                
                                # #3 "Strong but Safe (>15% Alpha)" (Filtered + Momentum)
                                sim_3 = run_sma_strategy(
                                    df, bench_df=sim_bench_df,
                                    investment_size=investment_per_stock, 
                                    trend_filter_sma200=True,
                                    min_trend_strength=0.15
                                )
                                
                                # Accumulate
                                total_strat1_pnl += sim_1.get("total_pnl", 0.0)
                                total_strat2_pnl += sim_2.get("total_pnl", 0.0)
                                total_strat3_pnl += sim_3.get("total_pnl", 0.0)
                                
                                # For Benchmark, we can take it from any sim result (they use same bench_df)
                                # Ensure we don't double count if strategies fail, but here we run all 3.
                                # Use sim_1's bench pnl
                                total_bh_bench_pnl += sim_1.get("bh_bench_pnl", 0.0)
                                
                                results_log.append({
                                    "Ticker": ticker,
                                    "Short Term": sim_1.get("total_pnl", 0.0),
                                    "Safety": sim_2.get("total_pnl", 0.0),
                                    "StrongSafe": sim_3.get("total_pnl", 0.0),
                                    "S&P500": sim_1.get("bh_bench_pnl", 0.0)
                                })
                                
                        except Exception as e:
                            print(f"Error analyzing {ticker}: {e}")
                            
                    status_text.text("Analysis Complete!")
                    progress_bar.empty()
                    
                    # Display Results
                    st.write(f"### 💰 Accumulated Gains (Invested ${investment_per_stock:,.0f} per stock)")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    
                    c1.metric("Short Term Trend", f"${total_strat1_pnl:,.0f}")
                    c2.metric("Long Term Safety", f"${total_strat2_pnl:,.0f}", delta=f"{total_strat2_pnl - total_strat1_pnl:,.0f} vs Short")
                    c3.metric("Strong >15%", f"${total_strat3_pnl:,.0f}", delta=f"{total_strat3_pnl - total_strat1_pnl:,.0f} vs Short")
                    c4.metric("Buy & Hold S&P500", f"${total_bh_bench_pnl:,.0f}", delta=None)

                    # Detailed Breakdown
                    with st.expander("View Detailed Breakdown"):
                        res_df = pd.DataFrame(results_log)
                        st.dataframe(res_df.style.format("${:,.0f}", subset=["Short Term", "Safety", "StrongSafe", "S&P500"]))
                
                st.divider()
                
                # Edit Section
                with st.expander("Edit Universe", expanded=False):
                    with st.form("edit_universe_form"):
                        edit_description = st.text_area("Description", u.description)
                        edit_tickers = st.text_area("Tickers (comma separated)", ", ".join(u.tickers), height=150)
                        
                        c_update, c_delete = st.columns([1, 1])
                        
                        submitted = st.form_submit_button("Update Universe")
                        if submitted:
                            tickers_list = [t.strip().upper() for t in edit_tickers.split(",") if t.strip()]
                            u.description = edit_description
                            u.tickers = tickers_list
                            manager.save_universe(u)
                            st.success("Universe updated successfully!")
                            st.rerun()
                
                # Delete Section (Separate from form to avoid conflicts)
                st.markdown("---")
                st.warning("Danger Zone")
                if st.button(f"Delete '{u.name}'", type="primary"):
                    manager.delete_universe(u.name)
                    st.success(f"Deleted '{u.name}'")
                    st.rerun()
                
                # Display Tickers
                st.subheader("Included Assets")
                st.write(", ".join(u.tickers))
