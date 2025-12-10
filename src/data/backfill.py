import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.config import Config
# Force Production Mode for consistent DB access
Config.USE_SYNTHETIC_DB = True
Config.DATA_STRATEGY = "PRODUCTION"

from src.data.ingestion import DataFetcher
from src.analytics.activity import ActivityTracker
from src.analytics.fusion import FusionEngine
from src.analytics.technical import add_technical_features
from src.analytics.metrics import calculate_relative_volume, calculate_volume_acceleration, calculate_volatility

def main():
    print("🚀 Starting Historical Score Backfill...")
    
    tracker = ActivityTracker()
    fetcher = DataFetcher() 
    fusion = FusionEngine()
    
    # 1. Gather Targets
    targets = set()
    
    # Favorites
    liked = tracker.get_liked_stocks()
    print(f"❤️ Found {len(liked)} liked stocks.")
    for item in liked:
        targets.add(item['ticker'])
        
    # Rising (Recent Views)
    rising = tracker.get_rising_pressure_stocks(limit=20)
    print(f"📈 Found {len(rising)} recent rising stocks.")
    for item in rising:
        targets.add(item['ticker'])
        
    target_list = sorted(list(targets))
    print(f"📋 Total Targets to Refresh: {len(target_list)}")
    
    if not target_list:
        print("Done.")
        return

    # 2. Processor
    success_count = 0
    
    collected_scores = {}

    for ticker in target_list:
        if ticker == "$MARKET": continue # Skip virtual ticker for now
        
        print(f"\n🔄 Processing {ticker}...")
        try:
            # A. Fetch Data (Force 1y to ensure depth)
            df = fetcher.fetch_ohlcv(ticker, period="1y")
            if df.empty or len(df) < 50:
                print(f"   ⚠️ Insufficient Data (Rows: {len(df)})")
                continue
                
            # B. Technicals
            df = add_technical_features(df)
            
            # C. Alt Data
            alt_df = fetcher.fetch_alt_data(ticker)
            att_norm = 0.0
            if not alt_df.empty and 'web_attention' in alt_df.columns:
                 # Clamp!
                 att_norm = min(1.0, alt_df.iloc[-1]['web_attention'] / 100.0)
            
            news_items = fetcher.fetch_news(ticker, limit=5)
            news_score = 0.0
            if news_items:
                s_scores = [n.get('sentiment_score', 0) for n in news_items if 'sentiment_score' in n]
                if s_scores:
                    news_score = sum(s_scores) / len(s_scores)
            
            # D. Metrics
            # Trend (RSI normalized)
            # 2. Key Metrics
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            from src.analytics.metrics import calculate_trend_strength
            trend_norm = calculate_trend_strength(df)
            
            # Volatility
            vol_norm = 0.5
            if not df.empty:
                returns = df['close'].pct_change().dropna()
                vol = calculate_volatility(returns).iloc[-1] if not returns.empty else 0.0
                vol_norm = min(1.0, vol * 2)
                
            # Volume Hybrid
            rel_vol = calculate_relative_volume(df, window=20)
            vol_acc = calculate_volume_acceleration(df, window=3)
            
            # E. Fusion
            score = fusion.calculate_pressure_score(
                price_trend=trend_norm,
                volatility_rank=vol_norm,
                sentiment_score=news_score,
                attention_score=att_norm,
                relative_volume=rel_vol,
                volume_acceleration=vol_acc
            )
            
            print(f"   ✅ Score: {score:.1f} (VolAcc: {vol_acc:.1%}, RelVol: {rel_vol:.1f})")
            
            # F. Update DB
            tracker.update_ticker_metadata(ticker, {"score": score, "last_updated": datetime.now().isoformat()})
            collected_scores[ticker] = score
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Calculate $MARKET Score (Aggregate)
    print("\n🌍 Calculating Global Market Score...")
    market_score = 50.0
    
    # Priority: SPY, QQQ, then Average
    if "SPY" in collected_scores and "QQQ" in collected_scores:
        market_score = (collected_scores["SPY"] + collected_scores["QQQ"]) / 2
    elif "SPY" in collected_scores:
        market_score = collected_scores["SPY"]
    elif collected_scores:
        market_score = sum(collected_scores.values()) / len(collected_scores)
        
    print(f"   ✅ Market Score: {market_score:.1f}")
    tracker.update_ticker_metadata("$MARKET", {"score": market_score, "last_updated": datetime.now().isoformat()})

    print(f"\n✨ Backfill Complete. Updated {success_count}/{len(target_list)} stocks + $MARKET.")

if __name__ == "__main__":
    main()
