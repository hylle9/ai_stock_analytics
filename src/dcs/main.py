
import time
import sys
import os
import signal
from datetime import datetime

# --- 1. ENVIRONMENT SETUP ---
# Because DCS runs as a standalone background process, we must manually 
# add the project root to the python path so imports work.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Internal Modules
from src.utils.config import Config
from src.data.ingestion import DataFetcher
from src.analytics.activity import ActivityTracker
from src.analytics.fusion import FusionEngine
from src.analytics.gemini_analyst import GeminiAnalyst
from src.analytics.insights import InsightManager
from src.models.portfolio import PortfolioManager
import db_dtypes # Ensures compatibility with DuckDB-Pandas conversions
import json
from src.analytics.metrics import calculate_relative_volume, calculate_volume_acceleration
from src.analytics.technical import add_technical_features
from src.analytics.backtester import run_sma_strategy
from src.data.relationships import RelationshipManager

# --- CONFIGURATION ---
LOG_FILE = os.path.join(Config.DATA_CACHE_DIR, "dcs_event.log")
# ---------------------

def log_event(ticker, event_type, status, details="", origin="UNKNOWN"):
    """
    Writes structured logs to a file.
    Format: [Timestamp] [Ticker] [Source] [Event] [Status] - Details
    Useful for debugging what the background service is doing.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not origin: origin = "UNKNOWN"
    entry = f"[{timestamp}] [{ticker}] [{origin}] [{event_type}] [{status}] - {details}\n"
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(entry)
    except Exception as e:
        print(f"❌ Log Error: {e}")

def signal_handler(sig, frame):
    """Handles graceful shutdown (CTRL+C)."""
    print("\n🛑 DCS Stopping...")
    sys.exit(0)

def is_market_hours() -> bool:
    """
    Checks if we are currently in 'High Frequency Mode' (Market Hours).
    Returns True if Mon-Fri, 9am - 6pm (Approximate Local Time).
    """
    now = datetime.now()
    if now.weekday() >= 5: return False # Weekend (Sat=5, Sun=6)
    
    # Simple check: 9:00 AM to 6:00 PM
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=18, minute=0, second=0, microsecond=0)
    return start <= now <= end

def main():
    """
    Main Data Collection Loop.
    This process runs indefinitely until stopped.
    It builds a list of targets, fetches updates, and saves them to the DB.
    """
    print("🚀 DCS: Data Collect Server Starting...")
    
    # --- CONFIGURATION OVERRIDES ---
    # We want DCS to ALWAYS act as the bridge between Live API and the Database.
    # So we force:
    # 1. USE_SYNTHETIC_DB = True (So we can write to the DuckDB file)
    # 2. DATA_STRATEGY = "LIVE" (So DataFetcher prefers API over existing cache)
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "LIVE" 
    
    # Initialize Components
    try:
        tracker = ActivityTracker() # Tracks what user likes/clicks
        fetcher = DataFetcher()     # Handles data downloading
        fusion = FusionEngine()     # Calculates scores
        gemini = GeminiAnalyst()    # AI wrapper
        insights = InsightManager() # Manages AI text reports
        pm = PortfolioManager()     # Loads user portfolios
        rm = RelationshipManager()  # Graph DB for discovery
    except Exception as e:
        print(f"❌ Failed to initialize components: {e}")
        return

    # register cleanup handler
    signal.signal(signal.SIGINT, signal_handler)

    # --- INFINITE LOOP ---
    while True:
        cycle_start = datetime.now()
        market_open = is_market_hours()
        print(f"\n⏰ --- Cycle Start: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')} (Market Open: {market_open}) ---")
        
        # --- 1. AGGREGATE TARGETS (What should we update?) ---
        # We don't update everything in the universe, only relevant stocks.
        update_targets = set()
        
        # A. Always update Benchmarks
        benchmarks = ["RSP", "SPY", "QQQ"]
        update_targets.update(benchmarks)
        
        # B. User Favorites (Liked Stocks)
        liked_stocks = tracker.get_liked_stocks() 
        for item in liked_stocks:
            update_targets.add(item['ticker'])
            
        # C. Portfolio Holdings
        try:
            # Refresh portfolio state from DB
            if Config.USE_SYNTHETIC_DB:
                pm.load_portfolios_from_db()
            else:
                pm.load_portfolios()
                
            portfolios = pm.list_portfolios()
            for p in portfolios:
                update_targets.update(p.holdings.keys())
        except Exception as e:
            print(f"⚠️ Portfolio Sync Error: {e}")
            
        # D. SPIDER MODE: Autonomous Discovery
        # Find NEW stocks related to the ones we already track.
        try:
            core_list = list(update_targets)
            # Ask Graph DB for neighbors (Competitors, Suppliers, etc)
            new_candidates = rm.get_discovery_candidates(core_list, limit=10, depth=Config.SPIDER_DEPTH)
            
            if new_candidates:
                print(f"🕷️ Spider Mode: Discovered {len(new_candidates)} new targets: {new_candidates}")
                update_targets.update(new_candidates)
                
                # Log discovery for debugging
                for c in new_candidates:
                    log_event(c, "DISCOVERY", "NEW_TARGET", "Relationship Expansion", "SPIDER")
        except Exception as e:
            print(f"Spider Error: {e}")

        # Convert to sorted list for execution stability
        target_list = sorted(list(update_targets))
        
        # Filter out corrupt/test tickers
        target_list = [t for t in target_list if not t.startswith("SYN")]
        
        pressure_scores = []
        
        if not target_list:
            print("ℹ️ No stocks found to update.")
        else:
            print(f"📋 Found {len(target_list)} unique targets.")
            
            # --- 2. EXECUTE UPDATES ---
            for ticker in target_list:
                print(f"🔄 Updating {ticker}...")
                
                # Identify Data Source (for logs)
                origin = "UNKNOWN"
                if fetcher.db:
                   origin = fetcher.db.get_asset_origin(ticker)
                
                # Default values for Fusion Score
                current_rsi = 50.0
                current_volatility = 0.5
                current_sentiment = 0.0
                current_attention = 0.5
                
                # A. Update Price History (Gap Filling)
                try:
                    # Smart Period Selection: Don't re-download history we already have.
                    fetch_period = "1y" # Default safety
                    if fetcher.db:
                        last_date_str = fetcher.db.get_latest_date(ticker)
                        if last_date_str:
                            last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                            days_diff = (datetime.now() - last_date).days
                            
                            if days_diff < 1:
                                fetch_period = None # Up to date!
                                print(f"   ✨ Data up-to-date (Last: {last_date_str})")
                            elif days_diff <= 2:
                                fetch_period = "5d" # Quick incremental update
                                print(f"   ⚡ Small Gap ({days_diff}d). Fetching 5d...")
                            elif days_diff <= 25:
                                fetch_period = "1mo"
                                print(f"   📅 Medium Gap ({days_diff}d). Fetching 1mo...")
                            else:
                                fetch_period = "1y" # Full sync needed
                                print(f"   🗓️ Large Gap ({days_diff}d). Fetching 1y...")
                        else:
                             print("   🆕 New Ticker. Fetching 1y history...")

                    # Perform Fetch (If needed)
                    if fetch_period:
                        df = fetcher.fetch_ohlcv(ticker, period=fetch_period, use_cache=False) 
                        if not df.empty:
                            print(f"   ✅ OHLCV Updated ({len(df)} rows)")
                            
                            # --- CALCULATE STRATEGY SIGNALS ---
                            try:
                                # Add Technicals (RSI, SMA) locally so we can score it
                                tech_df = add_technical_features(df.copy())
                                
                                if 'rsi' in tech_df.columns:
                                    current_rsi = tech_df['rsi'].iloc[-1]
                                
                                # Run Backtests to generate Recommendation (BUY/SELL)
                                # 1. Conservative Strategy
                                sim_res = run_sma_strategy(tech_df, trend_filter_sma200=True)
                                strategy_rec = "BUY" if sim_res.get("is_active") else "SELL"
                                
                                # 2. Aggressive Strategy (Strong Trend)
                                sim_strong = run_sma_strategy(tech_df, trend_filter_sma200=True, min_trend_strength=0.15)
                                strong_rec = "YES" if sim_strong.get("is_active") else "NO"
                            except Exception as ex_strat:
                                print(f"   ⚠️ Strategy Sim Error: {ex_strat}")
                                strategy_rec = "Unknown"
                        else:
                            log_event(ticker, "OHLCV", "FAIL", "Empty DataFrame", origin)
                except Exception as e:
                    print(f"   ❌ OHLCV Error: {e}")
                    log_event(ticker, "OHLCV", "ERROR", str(e), origin)
                
                # B. Fundamentals Profile (Name, Sector, Industry)
                # This could be optimized to run only once a month, but for now we check it.
                try:
                    prof = fetcher.get_company_profile(ticker)
                except Exception as e:
                    print(f"   ❌ Profile Error: {e}")

                # C. News Ingestion (Always Fresh)
                news_items = []
                try:
                    news_items = fetcher.fetch_news(ticker, limit=5)
                    # Calculate Simple Sentiment Score from Metadata
                    if news_items:
                         s_scores = [n.get('sentiment_score', 0) for n in news_items if 'sentiment_score' in n]
                         if s_scores:
                             current_sentiment = sum(s_scores) / len(s_scores)
                except Exception as e:
                     print(f"   ❌ News Error: {e}")

                # D. Alternative Data (Social & Web Attention)
                try:
                     alt_df = fetcher.fetch_alt_data(ticker, days=30)
                     if not alt_df.empty and 'web_attention' in alt_df.columns:
                         raw_att = alt_df.iloc[-1]['web_attention']
                         # Normalize heuristic (0-100 scale -> 0.0-1.0)
                         current_attention = min(1.0, raw_att / 100.0) 
                except Exception as e:
                    print(f"   ❌ Alt Data Error: {e}")

                # --- E. FUSION ENGINE (The Brain) ---
                try:
                    # Normalize inputs for the Fusion Equation
                    norm_trend = (current_rsi - 50) / 50.0
                    
                    # Calculate Volume Metrics (Rocket detection)
                    rel_vol = 1.0; vol_acc = 0.0
                    if 'df' in locals() and not df.empty:
                        rel_vol = calculate_relative_volume(df, window=20)
                        vol_acc = calculate_volume_acceleration(df, window=3)
                    
                    # Compute Unified Score
                    score = fusion.calculate_pressure_score(
                        price_trend=norm_trend,
                        volatility_rank=current_volatility, 
                        sentiment_score=current_sentiment,
                        attention_score=current_attention,
                        relative_volume=rel_vol,
                        volume_acceleration=vol_acc
                    )
                    pressure_scores.append(score)
                    
                    # Store Result in DB (Persistent Metadata)
                    meta_payload = {
                        "score": score, 
                        "last_updated": datetime.now().isoformat(),
                        "strategy_rec": strategy_rec if 'strategy_rec' in locals() else "Unknown",
                        "strong_rec": strong_rec if 'strong_rec' in locals() else "NO"
                    }
                    tracker.update_ticker_metadata(ticker, meta_payload)
                except Exception as e:
                    print(f"   ❌ Fusion Error: {e}")

                # --- F. AI GENERATION (Gemini) ---
                # We proactively generate "Research Clues" if they are missing/stale.
                try:
                    existing = insights.get_todays_insight(ticker, report_type="research_clues", valid_days=1)
                    if not existing:
                        print(f"   🧠 Generating AI Insight...")
                        
                        metrics = {
                            'rsi': current_rsi,
                            'sentiment_score': current_sentiment,
                            'attention_score': current_attention * 100,
                            'pressure_score': score
                        }
                        
                        # Generate text report
                        report = gemini.analyze_news(ticker, news_items, metrics)
                        
                        if report:
                            insights.save_insight(ticker, report, report_type="research_clues")
                            log_event(ticker, "GEMINI", "SUCCESS", "New Report", origin)
                except Exception as e:
                    pass # Silent fail is okay, don't crash main loop

                # Throttle requests to avoid API bans
                time.sleep(1.5) 

        # --- END OF CYCLE SUMMARY ---
        
        # 3. Calculate Global Market Weather
        if pressure_scores:
            avg_pressure = sum(pressure_scores) / len(pressure_scores)
            
            status = "NEUTRAL"
            if avg_pressure > 65: status = "OVERHEATED/BULLISH"
            elif avg_pressure < 35: status = "FEARFUL/BEARISH"
            
            print(f"\n📢 GLOBAL MARKET WEATHER: {status} (Score: {avg_pressure:.1f})")
            log_event("MARKET", "WEATHER", "UPDATE", f"{status} ({avg_pressure:.1f})")
            
            # Save global score to special '$MARKET' ticker
            tracker.update_ticker_metadata("$MARKET", {"score": avg_pressure, "status": status, "last_updated": datetime.now().isoformat()})
        
        # 4. Smart Sleep (Adaptive Frequency)
        if market_open:
            sleep_time = 900 # 15 mins (High frequency)
            print(f"⚡ Market Open. Sleeping for 15 mins...")
        else:
            sleep_time = 3600 # 1 hour (Low frequency)
            print(f"🌙 Market Closed. Sleeping for 1 hour...")
            
        time.sleep(sleep_time) 
            

if __name__ == "__main__":
    main()
