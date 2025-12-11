
import pandas as pd
from datetime import datetime

def generate_deep_dive_prompt(ticker: str, df: pd.DataFrame, news: list, indicators: dict) -> str:
    """
    Generates a comprehensive prompt for external AI analysis.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Price Context
    try:
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        change = ((current_price - prev_price) / prev_price) * 100
    except:
        current_price = 0.0
        change = 0.0
        
    # 2. Data Summary (Last 10 Days CSV)
    csv_data = "Date,Open,High,Low,Close,Volume\n"
    if not df.empty:
        # Get last 10 days, format nicely
        subset = df.tail(10).copy()
        # Ensure index is datetime
        if not pd.api.types.is_datetime64_any_dtype(subset.index):
             subset.index = pd.to_datetime(subset.index)
             
        for date, row in subset.iterrows():
            d_str = date.strftime("%Y-%m-%d")
            csv_data += f"{d_str},{row['open']:.2f},{row['high']:.2f},{row['low']:.2f},{row['close']:.2f},{row['volume']}\n"
            
    # 3. Formatted News
    news_str = ""
    for n in news[:5]: # Top 5
        title = n.get('title', 'No Title')
        pub = n.get('publisher', 'Unknown')
        link = n.get('link', '#')
        news_str += f"- [{pub}] {title} ({link})\n"
        
    # 4. Indicators Context
    rsi = indicators.get("rsi", "N/A")
    score = indicators.get("pressure_score", "N/A")
    
    prompt = f"""
You are a senior hedge fund analyst. I need a deep dive analysis on **{ticker}** as of {date_str}.

**Current Context:**
- **Price:** ${current_price:.2f} ({change:+.2f}%)
- **RSI:** {rsi}
- **Pressure Score:** {score}/100 (Proprietary Momentum Metric)

**Recent Market Data (Last 10 Days):**
```csv
{csv_data}
```

**Recent News Headlines:**
{news_str}

**Task:**
1. Analyze the technical structure based on the recent price action and volume.
2. Correlate the news headlines with the price movement.
3. Provide a specific trading plan:
   - **Bullish Scenario:** Buy Trigger, Stop Loss, Target.
   - **Bearish Scenario:** Short Trigger, Stop Loss, Target.
4. Rate the "Conviction Level" (High/Medium/Low).

Please be concise and direct.
    """
    return prompt.strip()
