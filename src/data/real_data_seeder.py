from src.data.db_manager import DBManager
import pandas as pd

class RealDataSeeder:
    """
    Populates DuckDB with top real-world assets to enable search.
    """
    def __init__(self):
        self.db = DBManager()
        
    def populate_top_assets(self):
        con = self.db.get_connection()
        print("🌱 Seeding Real Assets into DuckDB...")
        
        # Top 50 Stocks by Weight (Approx)
        top_assets = [
            ("AAPL", "Apple Inc.", "Technology"),
            ("MSFT", "Microsoft Corp.", "Technology"),
            ("NVDA", "Nvidia Corp.", "Technology"),
            ("AMZN", "Amazon.com Inc.", "Consumer Discretionary"),
            ("GOOGL", "Alphabet Inc. (Class A)", "Communication Services"),
            ("GOOG", "Alphabet Inc. (Class C)", "Communication Services"),
            ("META", "Meta Platforms Inc.", "Communication Services"),
            ("TSLA", "Tesla Inc.", "Consumer Discretionary"),
            ("BRK.B", "Berkshire Hathaway Inc.", "Financials"),
            ("LLY", "Eli Lilly and Co.", "Healthcare"),
            ("AVGO", "Broadcom Inc.", "Technology"),
            ("JPM", "JPMorgan Chase & Co.", "Financials"),
            ("V", "Visa Inc.", "Financials"),
            ("XOM", "Exxon Mobil Corp.", "Energy"),
            ("UNH", "UnitedHealth Group Inc.", "Healthcare"),
            ("MA", "Mastercard Inc.", "Financials"),
            ("PG", "Procter & Gamble Co.", "Consumer Staples"),
            ("JNJ", "Johnson & Johnson", "Healthcare"),
            ("HD", "Home Depot Inc.", "Consumer Discretionary"),
            ("MRK", "Merck & Co. Inc.", "Healthcare"),
            ("COST", "Costco Wholesale Corp.", "Consumer Staples"),
            ("ABBV", "AbbVie Inc.", "Healthcare"),
            ("AMD", "Advanced Micro Devices Inc.", "Technology"),
            ("CRM", "Salesforce Inc.", "Technology"),
            ("NFLX", "Netflix Inc.", "Communication Services"),
            ("PEP", "PepsiCo Inc.", "Consumer Staples"),
            ("KO", "Coca-Cola Co.", "Consumer Staples"),
            ("BAC", "Bank of America Corp.", "Financials"),
            ("WMT", "Walmart Inc.", "Consumer Staples"),
            ("TMO", "Thermo Fisher Scientific", "Healthcare"),
            ("LIN", "Linde plc", "Materials"),
            ("ACN", "Accenture plc", "Technology"),
            ("MCD", "McDonald's Corp.", "Consumer Discretionary"),
            ("DIS", "Walt Disney Co.", "Communication Services"),
            ("CSCO", "Cisco Systems Inc.", "Technology"),
            ("ABT", "Abbott Laboratories", "Healthcare"),
            ("ADBE", "Adobe Inc.", "Technology"),
            ("QCOM", "Qualcomm Inc.", "Technology"),
            ("CVX", "Chevron Corp.", "Energy"),
            ("VZ", "Verizon Communications", "Communication Services"),
            ("INTC", "Intel Corp.", "Technology"),
            ("CMCSA", "Comcast Corp.", "Communication Services"),
            ("PFE", "Pfizer Inc.", "Healthcare"),
            ("NKE", "Nike Inc.", "Consumer Discretionary"),
            ("WFC", "Wells Fargo & Co.", "Financials"),
            ("INTU", "Intuit Inc.", "Technology"),
            ("TXN", "Texas Instruments Inc.", "Technology"),
            ("PM", "Philip Morris International", "Consumer Staples"),
            ("DHR", "Danaher Corp.", "Healthcare"),
            ("UNP", "Union Pacific Corp.", "Industrials"),
        ]
        
        try:
            con.executemany(
                "INSERT OR IGNORE INTO dim_assets (ticker, name, sector) VALUES (?, ?, ?)", 
                top_assets
            )
            print("✅ Seeding Complete.")
        finally:
            con.close()

if __name__ == "__main__":
    seeder = RealDataSeeder()
    seeder.populate_top_assets()
