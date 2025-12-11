import google.generativeai as genai
from src.utils.config import Config
import os

class GeminiAnalyst:
    """
    Uses Google Gemini Pro to analyze financial news and provide qualitative insights.
    """
    def __init__(self):
        self.api_key = Config.GOOGLE_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            genai.configure(api_key=self.api_key)
            genai.configure(api_key=self.api_key)
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        else:
            self.model = None

    def _generate_synthetic_insight(self, ticker: str, context: str) -> str:
        """Generates a realistic-looking mock insight for Synthetic Mode when API is rate limited."""
        import random
        trend = random.choice(["Bullish", "Bearish", "Neutral"])
        rsi = random.uniform(30, 70)
        
        return f"""
### 🤖 Synthetic AI Insight ({ticker})
> **Note:** Real AI Rate Limit reached. Showing simulated data for testing.

*   **Trend Analysis:** The synthetic signals suggest a **{trend}** outlook.
*   **Technical Indicator:** RSI is effectively at **{rsi:.1f}**, indicating {trend} momentum.
*   **Recommendation:** This is a generated placeholder to allow you to continue testing the UI flow without burning API quota.
"""

    def _safe_get_text(self, response) -> str:
        """Safely extracts text from the response, handling errors/blocks."""
        try:
             # Check if parts exist
             if response.parts:
                 return response.text
             
             # Check finish reason if no parts
             # 1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
             reason = "UNKNOWN"
             if response.candidates and response.candidates[0].finish_reason:
                 reason = str(response.candidates[0].finish_reason)
                 
             if reason == "3" or "SAFETY" in reason: # Safety
                 return "⚠️ Insight unavailable: Content filtered by safety settings."
             
             if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                 # Try manual reconstruction if .text fails but parts exist deep down
                 return "".join([p.text for p in response.candidates[0].content.parts])
                 
             return f"⚠️ Insight unavailable (Empty Response). Finish Reason: {reason}"
        except ValueError as e:
            # Catch the specific "quick accessor" error
            return f"⚠️ Insight generation failed: {str(e)}"
        except Exception as e:
            return f"⚠️ Insight generation error: {str(e)}"

    def _safe_generate(self, prompt: str, ticker: str) -> str:
        if not self.model:
            return "Configuration Required: Please add GOOGLE_API_KEY to your .env file."
            
        try:
            response = self.model.generate_content(prompt)
            return self._safe_get_text(response)
        except Exception as e:
            err = str(e)
            if "429" in err or "Quota" in err:
                if Config.USE_SYNTHETIC_DB:
                    print(f"⚠️ Rate Limit. Returning Synthetic Insight for {ticker}.")
                    return self._generate_synthetic_insight(ticker, "Rate Limit")
                return f"Error: 429 Rate Limit Exceeded. Please wait 60s."
            return f"Error generating insight: {str(e)}"

    def analyze_news(self, ticker: str, news_items: list, metrics: dict) -> str:
        """
        Generates a summary explaining the connection between news and metrics.
        """
        if not news_items:
            return "No recent news available to analyze."
 
        # Prepare context for prompt
        headlines = [f"- {item.get('title')} ({item.get('publisher')})" for item in news_items[:10]]
        headlines_text = "\n".join(headlines)
        
        rsi = metrics.get('rsi', 50)
        sent = metrics.get('sentiment_score', 0)
        att = metrics.get('attention_score', 0)
        
        prompt = f"""
        You are a senior financial analyst. Analyze the following news headlines for {ticker} and connect them to the current quantitative signals.
        
        **Quantitative Signals:**
        - Trend (RSI): {rsi:.1f} (Over 70 is Overbought, Under 30 is Oversold)
        - News Sentiment Score: {sent:.2f} (Range -1 to 1)
        - Web Attention: {att:.0f}/100
        
        **Recent News Headlines:**
        {headlines_text}
        
        **Task:**
        Provide a concise "Research Clues" report (max 150 words).
        1. Identify the key narrative driving the stock.
        2. Explain if the news supports or contradicts the RSI/Sentiment scores.
        3. Highlight any specific "clues" (partnerships, warnings, earnings) that justify the Attention score.
        
        Format as markdown with bold points.
        """
        
        return self._safe_generate(prompt, ticker)

    def analyze_technicals(self, ticker: str, data: object) -> str:
        """
        Analyzes raw technical data to provide trends and buy/sell guidance.
        """
        # Convert dataframe to markdown table for the prompt
        try:
            table_md = data.to_markdown(index=True)
        except:
            table_md = str(data)
        
        prompt = f"""
        You are an expert Technical Analyst. I will provide you with the last few days of raw technical data for {ticker}.
        
        **Raw Data:**
        {table_md}
        
        **Task:**
        Interpret this data for a retail investor.
        1. **Explain the Indicators:** Briefly explain what the current values of RSI, MACD, Bollinger Bands (if present), and SMA mean FOR THIS STOCK right now. Do not give generic definitions.
        2. **Trend Analysis:** Is the stock trending up, down, or sideways based on these numbers?
        3. **Guidance:** Conclude with a clear Buy, Hold, or Sell assessment based PURELY on this technical data.
        
        Keep it concise, professional, and easy to read. Use bullet points.
        **CRITICAL: Do NOT use LaTeX or Math formatting for numbers (e.g. no $x$ or \(x\)). Use standard text only.**
        """
        
        return self._safe_generate(prompt, ticker)

    def perform_deep_research(self, ticker: str, news_items: list, metrics: dict) -> str:
        """
        Conducts a 'Deep Research' session using Gemini 1.5 Pro (if avail) or best model.
        Focuses on Industry, Competitors, and resolving Mixed Signals.
        """
        if not self.api_key:
             return "Configuration Required: Please add GOOGLE_API_KEY to your .env file."

        if not news_items:
            news_items = []
            
        headlines = [f"- {item.get('title')} ({item.get('publisher')}) [{item.get('providerPublishTime')}]" for item in news_items[:40]]
        headlines_text = "\n".join(headlines)
        
        rsi = metrics.get('rsi', 50)
        alpha_50 = metrics.get('alpha_50', 0)
        score = metrics.get('pressure_score', 50)
        
        prompt = f"""
        You are a Principal Investment Researcher at a top-tier hedge fund. 
        Your task is to produce a "Deep Dive Strategic Report" for **{ticker}**.
        
        **Context:**
        - The user has requested this report because there are implied "Mixed Signals" or the stock is "Beating the Market" ({alpha_50:+.1%} Alpha) but needs verification.
        - Current Pressure Score: {score}/100.
        - RSI: {rsi:.1f}.
        
        **Available Intelligence (Recent Headlines):**
        {headlines_text}
        
        **Analysis Requirements (Detailed & Professional):**
        1. **Executive Thesis:** What is the specific argument for owning or selling this asset NOW? (High Confidence).
        2. **Industry & Competitive Landscape:** How is {ticker} positioned against key rivals? Are they gaining or losing moat?
        3. **Technological & Structural Shifts:** What macro or tech trends (AI, Green Energy, Rates) are specifically impacting their forward earnings?
        4. **"Mixed Signal" Resolution:** If price action contradicts news flow (or vice versa), explain WHY. Is the market wrong, or is the news priced in?
        5. **Verdict:** definitive Buy, Hold, or Sell with a timeline (6-12 months).
        
        **Format:**
        - Use professional markdown.
        - Use ## Headers.
        - No fluff. Focus on unique insights, not generic descriptions.
        """
        
        # Robust Model Selection with Fallback (Updated based on available models)
        candidates = ["gemini-1.5-pro", "gemini-2.5-flash"]
        
        last_error = None
        for model_name in candidates:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return self._safe_get_text(response)
            except Exception as e:
                err_str = str(e)
                # Fail fast on Rate Limits (Quota) to avoid burning retries on shared quota
                if "429" in err_str or "Quota" in err_str or "quota" in err_str:
                     if Config.USE_SYNTHETIC_DB:
                         return self._generate_synthetic_insight(ticker, "Deep Research Rate Limit")
                     return "⚠️ **Rate Limit Hit**: Gemini Free Tier quota exceeded. Please wait ~60 seconds and try again."
                
                last_error = e
                continue
                
        return f"Error conducting deep research: All models failed. Last error: {str(last_error)}"
