from textblob import TextBlob
import pandas as pd
from datetime import datetime

class SentimentAnalyzer:
    """
    Analyzes sentiment of text using TextBlob.
    """
    def analyze_news(self, news_items: list) -> float:
        """
        Calculate average sentiment score (-1 to 1) for a list of news items.
        """
        if not news_items:
            return 0.0
        
        scores = []
        for item in news_items:
            title = item.get('title', '')
            if title:
                blob = TextBlob(title)
                scores.append(blob.sentiment.polarity)
        
        if not scores:
            return 0.0
            
        return sum(scores) / len(scores)

    def get_sentiment_label(self, score: float) -> str:
        if score > 0.1:
            return "Positive"
        elif score < -0.1:
            return "Negative"
        else:
            return "Neutral"
