import time
from typing import List, Set
from src.data.ingestion import DataFetcher
from src.data.relationships import RelationshipManager
from src.data.db_manager import DBManager
from src.analytics.activity import ActivityTracker
from src.models.portfolio import PortfolioManager, PortfolioStatus
from src.utils.config import Config

class StockRetrievalSystem:
    """
    Orchestrates the 3-step stock retrieval process:
    1. RBRS (Rules Based): Favorites + Portfolio Holdings
    2. AIRS (AI Related): Competitors of RBRS
    3. NRRS (News Related): Tickers mentioned in news of RBRS/AIRS
    """
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.rel_manager = RelationshipManager()
        self.tracker = ActivityTracker()
        self.pm = PortfolioManager()
        
        # We need direct DB access to update origin tags
        if Config.USE_SYNTHETIC_DB:
             self.db = DBManager()
        else:
             self.db = None
        
    def run_full_cycle(self, competitor_limit: int = 5, news_limit: int = 5, dry_run: bool = False):
        """
        Executes the full retrieval cycle.
        :param competitor_limit: Max competitors to fetch per stock (up to 10 supported by prompt).
        :param news_limit: Max news articles to analyze per stock for NRRS.
        :param dry_run: If True, does not actually fetch market data, just logs discovery.
        """
        print("🚀 Starting Stock Retrieval Cycle...")
        
        # --- Step 1: RBRS (Rules Based Retrieval Stock) ---
        rbrs_tickers = self._get_rbrs_tickers()
        print(f"✅ RBRS: Found {len(rbrs_tickers)} seed tickers: {list(rbrs_tickers)}")
        self._tag_tickers(rbrs_tickers, "RBRS")
        
        # --- Step 2: AIRS (AI Based Retrieval Stock) ---
        airs_tickers = self._get_airs_tickers(rbrs_tickers, limit=competitor_limit)
        print(f"✅ AIRS: Found {len(airs_tickers)} competitor tickers: {list(airs_tickers)}")
        self._tag_tickers(airs_tickers, "AIRS")
        
        # --- Step 3: NRRS (News Related Retrieval Stock) ---
        # We search news for both RBRS and AIRS to cast a wide net
        combined_seeds = rbrs_tickers.union(airs_tickers)
        nrrs_tickers = self._get_nrrs_tickers(combined_seeds, limit=news_limit)
        print(f"✅ NRRS: Found {len(nrrs_tickers)} news-related tickers: {list(nrrs_tickers)}")
        self._tag_tickers(nrrs_tickers, "NRRS")
        
        # --- Step 4: Consolidation & Fetching ---
        all_tickers = rbrs_tickers.union(airs_tickers).union(nrrs_tickers)
        print(f"📦 Total Unique Tickers to Process: {len(all_tickers)}")
        
        if not dry_run:
            self._fetch_market_data(all_tickers)
            
        print("🏁 Stock Retrieval Cycle Completed.")
        return {
            "rbrs": list(rbrs_tickers),
            "airs": list(airs_tickers),
            "nrrs": list(nrrs_tickers),
            "total": list(all_tickers)
        }

    def _tag_tickers(self, tickers: Set[str], origin: str):
        """Updates the retrieval_origin in DB."""
        if self.db:
            for t in tickers:
                self.db.update_asset_origin(t, origin)

    def _get_rbrs_tickers(self) -> Set[str]:
        """Collects tickers from Favorites and Active Portfolios."""
        tickers = set()
        
        # 1. Favorites
        favs = self.tracker.get_liked_stocks()
        for f in favs:
            tickers.add(f['ticker'])
            
        # 2. Portfolios (Includes all for broad context)
        for p in self.pm.list_portfolios():
            for t in p.holdings.keys():
                tickers.add(t)
                
        return tickers

    def _get_airs_tickers(self, seeds: Set[str], limit: int) -> Set[str]:
        """Finds competitors for the seed tickers."""
        competitors = set()
        
        for ticker in seeds:
            # Check if we already have competitors in DB/Cache
            existing_comps = self.rel_manager.get_competitors(ticker)
            
            # If few competitors, trigger AI expansion
            if len(existing_comps) < 3 and Config.GOOGLE_API_KEY:
                print(f"   🧠 Expanding knowledge for {ticker}...")
                if self.rel_manager.expand_knowledge(ticker):
                    existing_comps = self.rel_manager.get_competitors(ticker)
            
            # Add up to limit
            for c in existing_comps[:limit]:
                competitors.add(c)
                
        return competitors

    def _get_nrrs_tickers(self, seeds: Set[str], limit: int) -> Set[str]:
        """Extracts new tickers mentioned in news articles of seed tickers."""
        discovered = set()
        
        if not Config.GOOGLE_API_KEY:
            return discovered
            
        for ticker in seeds:
            # Fetch recent news
            news = self.fetcher.fetch_news(ticker, limit=limit)
            
            for article in news:
                # We prioritize the title for extraction cost/speed
                text_to_analyze = f"{article.get('title', '')}"
                
                # If we have a summary or content, maybe add it (careful with token limits)
                # content = article.get('summary', '') 
                
                found = self.rel_manager.extract_tickers_from_text(text_to_analyze)
                if found:
                    print(f"   📰 Found {found} in news for {ticker}")
                    for f in found:
                        # Avoid adding the seed ticker itself (noise)
                        if f != ticker:
                            discovered.add(f)
                            
        return discovered

    def _fetch_market_data(self, tickers: Set[str]):
        """Ensures market data exists for all tickers."""
        total = len(tickers)
        for idx, ticker in enumerate(tickers):
            print(f"   ⬇️ [{idx+1}/{total}] Fetching data for {ticker}...")
            # Fetch OHLCV (Daily)
            self.fetcher.fetch_ohlcv(ticker, period="1y")
            # Fetch Profile/Fundamentals (if new)
            self.fetcher.get_company_profile(ticker)
            self.fetcher.get_fundamentals(ticker)
