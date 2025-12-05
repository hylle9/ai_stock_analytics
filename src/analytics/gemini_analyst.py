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
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

    def analyze_news(self, ticker: str, news_items: list, metrics: dict) -> str:
        """
        Generates a summary explaining the connection between news and metrics.
        
        Args:
            ticker: Stock symbol
            news_items: List of news dictionaries
            metrics: Dict containing 'rsi', 'sentiment_score', 'attention_score'
        """
        if not self.model:
            return "Configuration Required: Please add GOOGLE_API_KEY to your .env file to enable AI Research Clues."
            
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
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating AI insight: {str(e)}"
