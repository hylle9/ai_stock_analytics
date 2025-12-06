import yfinance as yf

def check_info(ticker):
    t = yf.Ticker(ticker)
    info = t.info
    print(f"--- {ticker} ---")
    keys_to_check = ['sector', 'industry', 'competitors', 'related', 'recommendedSymbols']
    for k in keys_to_check:
        print(f"{k}: {info.get(k)}")
    
    # Check if there is a 'sector' key at all
    print(f"Sector in keys: {'sector' in info}")

check_info("AAPL")
check_info("MSFT")
