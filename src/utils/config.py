import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Central configuration for the application.
    """
    # API Keys
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    
    # Data Settings
    DATA_CACHE_DIR = os.getenv("DATA_CACHE_DIR", "data/raw")
    USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "False").lower() == "true"
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    
    USE_SYNTHETIC_DB = False
    DATA_STRATEGY = "LEGACY" # "LEGACY", "SYNTHETIC", "LIVE", "PRODUCTION"

    # Feature Flags
    ENABLE_REAL_SENTIMENT = os.getenv("ENABLE_REAL_SENTIMENT", "True").lower() == "true"

    @classmethod
    def validate(cls):
        """
        Validate critical configuration.
        """
        if not cls.ALPHA_VANTAGE_API_KEY and not cls.USE_MOCK_DATA:
            print("WARNING: ALPHA_VANTAGE_API_KEY not set. Real data fetching may fail.")
