from typing import List

# Default Universe Configuration
DEFAULT_UNIVERSE_NAME = "Big_Tech_10"
DEFAULT_UNIVERSE_DESCRIPTION = "Top 10 US Tech stocks"
DEFAULT_UNIVERSE_TICKERS: List[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", 
    "META", "TSLA", "NFLX", "AMD", "INTC"
]

# API Configuration
API_TIMEOUT_SECONDS = 10
MAX_NEWS_ITEMS = 50
CACHE_EXPIRY_HOURS = 24

# Data Ingestion
DEFAULT_HISTORY_PERIOD = "2y"
ALT_DATA_HISTORY_DAYS = 30
