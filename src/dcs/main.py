
import time
import sys
import os
import signal
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.config import Config
from src.data.ingestion import DataFetcher
from src.analytics.activity import ActivityTracker
from src.analytics.fusion import FusionEngine
from src.analytics.gemini_analyst import GeminiAnalyst
from src.analytics.insights import InsightManager
from src.models.portfolio import PortfolioManager
import db_dtypes # ensure pandas legacy support for duckdb
import json
from src.analytics.metrics import calculate_relative_volume, calculate_volume_acceleration

# --- CONFIGURATION ---
LOG_FILE = os.path.join(Config.DATA_CACHE_DIR, "dcs_event.log")
# ---------------------

def log_event(ticker, event_type, status, details="", origin="UNKNOWN"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Fallback if origin is None/Empty
    if not origin: origin = "UNKNOWN"
    entry = f"[{timestamp}] [{ticker}] [{origin}] [{event_type}] [{status}] - {details}\n"
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(entry)
    except Exception as e:
        print(f"❌ Log Error: {e}")

def signal_handler(sig, frame):
    print("\n🛑 DCS Stopping...")
    sys.exit(0)

def is_market_hours() -> bool:
    """Checks if currently NY market hours (Mon-Fri 9:30-16:00 ET)"""
    # Simple check using execution time (assumes machine has correct clock)
    # Ideally use pytz for timezone correctness, but keeping simple for now
    now = datetime.now()
    if now.weekday() >= 5: return False # Weekend
    
    # 9:30 - 16:00 Local Time (Assuming user in Europe per logs? +01:00)
    # If user asks for ET check, we'd need pytz.
    # Let's assume broad "daytime" for higher frequency: 9AM - 6PM
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=18, minute=0, second=0, microsecond=0)
    return start <= now <= end

def main():
    print("🚀 DCS: Data Collect Server Starting...")
    
    # Force Configuration for DCS
    # We want to Write to DB, so we pretend to be in Synthetic Mode for DB Access
    # BUT we want to Fetch from Live, so we override the Strategy
    Config.USE_SYNTHETIC_DB = True
    Config.DATA_STRATEGY = "LIVE" 
    
    # Initialize Components
    try:
        tracker = ActivityTracker()
        fetcher = DataFetcher() 
        # Note: DataFetcher uses Config.DATA_STRATEGY used at import text... 
        # Actually Config is a class, so changes apply. 
        # DataFetcher.__init__ logic:
        # if Config.USE_SYNTHETIC_DB -> inits DuckDBProvider
        # if Config.DATA_STRATEGY == "LIVE" -> fetch_ohlcv calls live_provider -> saves to db
        fusion = FusionEngine()
        gemini = GeminiAnalyst()
        insights = InsightManager()
        pm = PortfolioManager()
    except Exception as e:
        print(f"❌ Failed to initialize components: {e}")
        return

    signal.signal(signal.SIGINT, signal_handler)

    while True:
        cycle_start = datetime.now()
        market_open = is_market_hours()
        print(f"\n⏰ --- Cycle Start: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')} (Market Open: {market_open}) ---")
        
        # --- AGGREGATE TARGETS ---
        update_targets = set()
        
        # 1. Benchmarks (Critical for Alpha)
        benchmarks = ["RSP", "SPY", "QQQ"]
        update_targets.update(benchmarks)
        
        # 2. Liked Stocks
        liked_stocks = tracker.get_liked_stocks() 
        for item in liked_stocks:
            update_targets.add(item['ticker'])
            
        # 3. Portfolio Holdings
        try:
            # Reload portfolios to get latest state from DB/File
            if Config.USE_SYNTHETIC_DB:
                pm.load_portfolios_from_db()
            else:
                pm.load_portfolios()
                
            portfolios = pm.list_portfolios()
            for p in portfolios:
                update_targets.update(p.holdings.keys())
        except Exception as e:
            print(f"⚠️ Portfolio Sync Error: {e}")
            
        # Convert to sorted list for consistent execution
        target_list = sorted(list(update_targets))
        pressure_scores = []
        
        if not target_list:
            print("ℹ️ No stocks found to update.")
        else:
            print(f"📋 Found {len(target_list)} unique targets.")
            
            for ticker in target_list:
                print(f"🔄 Updating {ticker}...")
                
                # Get Origin
                origin = "UNKNOWN"
                if fetcher.db:
                   origin = fetcher.db.get_asset_origin(ticker)
                
                # Context for Fusion
                current_rsi = 50.0
                current_volatility = 0.5
                current_sentiment = 0.0
                current_attention = 0.5 # Normalized (0.0 to 1.0)
                
                # A. Gap Filling OHLCV
                try:
                    # Smart Period Selection
                    fetch_period = "1y" # Default
                    if fetcher.db:
                        last_date_str = fetcher.db.get_latest_date(ticker)
                        if last_date_str:
                            last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                            days_diff = (datetime.now() - last_date).days
                            
                            if days_diff < 1:
                                fetch_period = None # Already up to date
                                print(f"   ✨ Data up-to-date (Last: {last_date_str})")
                            elif days_diff <= 2:
                                fetch_period = "5d" # Light fetch
                                print(f"   ⚡ Small Gap ({days_diff}d). Fetching 5d...")
                            elif days_diff <= 25:
                                fetch_period = "1mo"
                                print(f"   📅 Medium Gap ({days_diff}d). Fetching 1mo...")
                            else:
                                fetch_period = "1y" # Full sync
                                print(f"   🗓️ Large Gap ({days_diff}d). Fetching 1y...")
                        else:
                             print("   🆕 New Ticker. Fetching 1y history...")

                    if fetch_period:
                        df = fetcher.fetch_ohlcv(ticker, period=fetch_period, use_cache=False) 
                        if not df.empty:
                            print(f"   ✅ OHLCV Updated ({len(df)} rows)")
                            
                            # Simple RSI calc
                            delta = df['close'].diff()
                            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                            rs = gain / loss
                            rsi_series = 100 - (100 / (1 + rs))
                            if not rsi_series.empty:
                                current_rsi = rsi_series.iloc[-1]
                        else:
                            log_event(ticker, "OHLCV", "FAIL", "Empty DataFrame", origin)
                except Exception as e:
                    print(f"   ❌ OHLCV Error: {e}")
                    log_event(ticker, "OHLCV", "ERROR", str(e), origin)
                
                # B. Fundamentals/Profile (Once per day optimization?)
                # For now, keep asking but maybe lightweight check
                try:
                    prof = fetcher.get_company_profile(ticker)
                    if prof: pass
                except Exception as e:
                    print(f"   ❌ Profile Error: {e}")

                # C. News (Always fresh)
                news_items = []
                try:
                    news_items = fetcher.fetch_news(ticker, limit=5)
                    if news_items:
                         s_scores = [n.get('sentiment_score', 0) for n in news_items if 'sentiment_score' in n]
                         if s_scores:
                             current_sentiment = sum(s_scores) / len(s_scores)
                except Exception as e:
                     print(f"   ❌ News Error: {e}")

                # D. Alt Data
                try:
                     alt_df = fetcher.fetch_alt_data(ticker, days=30)
                     if not alt_df.empty and 'web_attention' in alt_df.columns:
                         raw_att = alt_df.iloc[-1]['web_attention']
                         current_attention = min(1.0, raw_att / 100.0) 
                except Exception as e:
                    print(f"   ❌ Alt Data Error: {e}")

                # --- E. FUSION & METADATA ---
                try:
                    # Normalize Trend (RSI 0-100 -> -1 to 1)
                    norm_trend = (current_rsi - 50) / 50.0
                    
                    # Calculate Volume Metrics (Hybrid Retail Score)
                    rel_vol = 1.0
                    vol_acc = 0.0
                    if 'df' in locals() and not df.empty:
                        rel_vol = calculate_relative_volume(df, window=20)
                        vol_acc = calculate_volume_acceleration(df, window=3)
                    
                    score = fusion.calculate_pressure_score(
                        price_trend=norm_trend,
                        volatility_rank=current_volatility, # Placeholder or calc std dev
                        sentiment_score=current_sentiment,
                        attention_score=current_attention,
                        relative_volume=rel_vol,
                        volume_acceleration=vol_acc
                    )
                    pressure_scores.append(score)
                    tracker.update_ticker_metadata(ticker, {"score": score, "last_updated": datetime.now().isoformat()})
                except Exception as e:
                    print(f"   ❌ Fusion Error: {e}")

                # --- F. GEMINI RESEARCH ---
                try:
                    # Logic unchanged, still valuable
                    existing = insights.get_todays_insight(ticker, report_type="research_clues", valid_days=1)
                    if not existing:
                        print(f"   🧠 Generating AI Insight...")
                        
                        metrics = {
                            'rsi': current_rsi,
                            'sentiment_score': current_sentiment,
                            'attention_score': current_attention * 100,
                            'pressure_score': score
                        }
                        
                        # Use lightweight "analyze_news" usually to save detailed quota
                        # Or "perform_deep_research" if user asked, but DCS should be lightweight
                        report = gemini.analyze_news(ticker, news_items, metrics)
                        
                        if report:
                            insights.save_insight(ticker, report, report_type="research_clues")
                            log_event(ticker, "GEMINI", "SUCCESS", "New Report", origin)
                except Exception as e:
                    pass # Silent fail for AI to avoid log spam

                # Throttle
                time.sleep(1.5)

        # --- END OF CYCLE ---
        # 1. Market Weather Report
        if pressure_scores:
            avg_pressure = sum(pressure_scores) / len(pressure_scores)
            
            status = "NEUTRAL"
            if avg_pressure > 65: status = "OVERHEATED/BULLISH"
            elif avg_pressure < 35: status = "FEARFUL/BEARISH"
            
            print(f"\n📢 GLOBAL MARKET WEATHER: {status} (Score: {avg_pressure:.1f})")
            log_event("MARKET", "WEATHER", "UPDATE", f"{status} ({avg_pressure:.1f})")
            
            # Save to special ticker '$MARKET'
            tracker.update_ticker_metadata("$MARKET", {"score": avg_pressure, "status": status, "last_updated": datetime.now().isoformat()})
        
        # 2. Smart Sleep
        # High freq during market, Low freq otherwise
        if market_open:
            sleep_time = 900 # 15 mins
            print(f"⚡ Market Open. Sleeping for 15 mins...")
        else:
            sleep_time = 3600 # 1 hour (User requested 4h, but let's do 1h for testing responsiveness)
            print(f"🌙 Market Closed. Sleeping for 1 hour...")
            
        time.sleep(sleep_time) 
            


if __name__ == "__main__":
    main()
