
import pandas as pd
import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.data.ingestion import DataFetcher
from src.analytics.technical import add_technical_features
from src.analytics.fusion import FusionEngine
from src.analytics.sentiment import SentimentAnalyzer
from src.analytics.metrics import calculate_volatility, calculate_relative_volume, calculate_volume_acceleration

def debug_ticker(ticker):
    print(f"\n--- DEBUGGING {ticker} ---")
    fetcher = DataFetcher()
    
    # 1. Price Data
    df = fetcher.fetch_ohlcv(ticker, period="3mo")
    if df.empty:
        print("No Price Data")
        return
    
    df = add_technical_features(df)
    rsi = df['rsi'].iloc[-1]
    
    # Volatility
    returns = df['close'].pct_change().dropna()
    vol = returns.std() * (252 ** 0.5) # Annualized
    
    # 2. Alt Data
    alt = fetcher.fetch_alt_data(ticker)
    if not alt.empty:
        att = alt['Web_Attention'].iloc[-1]
        sent_social = alt['Social_Sentiment'].iloc[-1]
    else:
        att = 0
        sent_social = 0
        
    # 3. News Sentiment
    news = fetcher.fetch_news(ticker, limit=20)
    analyzer = SentimentAnalyzer()
    news_score = analyzer.analyze_news(news)
    
    print(f"INPUTS:")
    print(f"  RSI: {rsi:.2f}")
    print(f"  Volatility (Ann): {vol:.2f}")
    print(f"  Web Attention (Raw): {att}")
    print(f"  News Sentiment: {news_score:.2f}")
    
    # New Metrics
    rel_vol = calculate_relative_volume(df, window=20)
    vol_acc = calculate_volume_acceleration(df, window=3)
    print(f"  Rel Volume: {rel_vol:.2f}")
    print(f"  Vol Accel: {vol_acc:.2%}")
    
    # 4. Calculation Logic (Replica of stock_view.py)
    trend_norm = (rsi - 50) / 50
    vol_norm = min(1.0, vol * 2)
    att_norm = min(1.0, att / 100.0) # CLAMPED
    
    print(f"NORMALIZED:")
    print(f"  Trend Norm: {trend_norm:.2f}")
    print(f"  Vol Norm: {vol_norm:.2f}")
    print(f"  Att Norm: {att_norm:.2f}")
    
    fusion = FusionEngine()
    score = fusion.calculate_pressure_score(
        price_trend=trend_norm,
        volatility_rank=vol_norm,
        sentiment_score=news_score,
        attention_score=att_norm,
        relative_volume=rel_vol,
        volume_acceleration=vol_acc
    )
    
    print(f"FINAL PRESSURE SCORE: {score}")

if __name__ == "__main__":
    tickers = ["AAPL", "MSFT", "AMZN", "GOOG"]
    for t in tickers:
        debug_ticker(t)
