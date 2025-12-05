from src.analytics.gemini_analyst import GeminiAnalyst
from src.utils.config import Config
import os
from unittest.mock import MagicMock, patch

def test_gemini_integration():
    # Test 1: No Key
    print("Test 1: Testing without API Key...")
    if 'GOOGLE_API_KEY' in os.environ:
        del os.environ['GOOGLE_API_KEY']
    Config.GOOGLE_API_KEY = None # runtime override
    
    analyst = GeminiAnalyst()
    response = analyst.analyze_news("TEST", [], {})
    print(f"Response (No Key): {response[:50]}...")
    assert "Configuration Required" in response

    # Test 2: With Key (Mocked)
    print("\nTest 2: Testing with Mocked Key...")
    Config.GOOGLE_API_KEY = "dummy_key"
    with patch('google.generativeai.GenerativeModel') as MockModel:
        instance = MockModel.return_value
        instance.generate_content.return_value.text = "Mocked Insight: Bullish trend."
        
        analyst = GeminiAnalyst()
        res = analyst.analyze_news("TEST", [{'title': 'Good News', 'publisher': 'Test'}], {'rsi': 60})
        print(f"Response (With Key): {res}")
        assert "Mocked Insight" in res

    print("\nSUCCESS: Gemini Analyst logic verified.")

if __name__ == "__main__":
    test_gemini_integration()
