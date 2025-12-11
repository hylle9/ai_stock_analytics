# AI Stock Analytics (ASA)

<div align="center">
  <h3>Institutional-Grade Market Intelligence for Everyone</h3>
  <p>Multi-Modal Analysis • Deep AI Research • Portfolio Management • Risk Analytics</p>
</div>

---

## 🚀 Project Overview

**AI Stock Analytics (ASA)** is an advanced market analysis platform designed to bridge the gap between retail trading tools and institutional-grade intelligence. At its core is the **"Fusion Engine"**, a sophisticated system that synthesizes multi-modal data streams into actionable insights.

Unlike simple chart wrappers or basic screeners, **ASA** treats the market as a complex adaptive system, analyzing it through four distinct lenses:
1.  **Price Action (Technical)**: Momentum, trend stability, and volatility energy.
2.  **Market Psychology (Sentiment)**: Real-time social sentiment and web search intensity.
3.  **Fundamental Context (Valuation)**: P/E ratios, earnings context, and sector benchmarking.
4.  **Macro Alpha (Relative Performance)**: Measuring performance against the broader market (S&P 500) to isolate idiosyncratic strength.

The system aggregates these disparate signals into a unified **"Pressure Score"** (0-100), a single metric that helps you identify high-probability opportunities where retail enthusiasm aligns with technical strength and fundamental safety.

> **Current Status**: Pre-Alpha / Active Development

---

## ✨ Key Features

### 🧠 1. Deep Research Agent (Gemini Powered)
Go beyond simple numbers with our integrated **AI Analyst**.
*   **On-Demand Intelligence**: Generates comprehensive research reports using **Google Gemini Pro**.
*   **Context-Aware**: The AI "sees" the exact metrics you are looking at (RSI, Volatility, Sentiment) to provide grounded analysis.
*   **Smart Caching**: "Weekly Research" reports are cached for 7 days to prevent analysis fatigue and conserve API quotas.
*   **Strategic Outlook**: Provides clear "Bull Case", "Bear Case", and "Execution Strategy" sections.

### ⚡ 2. Sub-Second Performance Architecture
We have engineered a high-performance data pipeline to ensure instant decision making:
*   **Consolidated Caching**: A unified data loader bundles Price, News, Fundamentals, and AI into a single transaction with a 1-hour TTL.
*   **Parallel Processing**: Peer benchmarks and competitor data are fetched in parallel batches, reducing load times from ~20s to <0.5s.
*   **Smart Persistence**: `DuckDB` based storage ensures data survives restarts, with automatic schema migrations to keep your database healthy.

### 📈 3. "Golden Cross" & Technical Visualization
*   **Golden Cross Indicators**: Automatically detects and visualizes the "Golden Cross" (SMA50 > SMA200) and "Death Cross" events.
*   **Trend Confirmation**: Color-coded crossover markers directly on the price chart.
*   **Contextual Scaling**: Benchmark (S&P 500) comparison is visually scaled to the stock's starting price for accurate relative performance tracking.

### 💎 4. The "Fusion Engine" & Pressure Score
Our proprietary scoring system quantifies the directional energy of a stock. It is not just a technical indicator; it is a composite signal of market intent.

**Composition (Hybrid Model):**
*   **Price Trend (30%)**: Normalized momentum (RSI, ROC, SMA Deviations).
*   **Volatility Energy (20%)**: Measures latent kinetic energy (Bollinger Band compression).
*   **Hybrid Retail Score (50%)**: A robust combination of:
    *   **Social Sentiment**: Real-time social chatter (StockTwits).
    *   **Volume Anomalies**: Spike detection (> 20-day avg).
    *   **Volume Acceleration**: 3-day rate-of-change.

**Pressure Score Guide:**
*   🟢 **> 70 (High Momentum)**: Strong Buy zone. Price is likely trending above SMA50 with high social volume.
*   🟡 **40-70 (Neutral)**: Consolidation / Holding pattern.
*   🔴 **< 40 (Weakness)**: Sell / Avoid zone. Price is likely below SMA200 with negative sentiment.

### 🧬 5. Multi-Strategy Simulation Engine
Test your thesis before risking capital with our professional-grade backtester:
*   **Dual-Strategy Comparison**: Compare "Aggressive" (Short-Term Trend) vs. "Conservative" (Long-Term Safety) strategies side-by-side.
*   **Delayed Entry Logic**: The Safety strategy features intelligent "Re-Entry" logic, ensuring you don't miss major bull runs just because the initial crossover was filtered out.
*   **Actionable Signals**: Real-time "Buy" / "Sell" recommendations displayed directly on the dashboard based on the current strategy state.
*   **Smart Benchmarking**: Apples-to-apples comparison against Buy & Hold (Stock) and the S&P 500 (Market) over the exact same time window.
*   **Universe Analysis**: Run comprehensive yearly simulations across entire sectors to identify the most profitable strategies for a group of stocks.

### 🕷️ 6. Spider Mode (Autonomous Discovery)
The system doesn't just analyze what you tell it to; it actively expands its own knowledge graph.
*   **Neighbor Discovery**: Automatically identifies competitors and supply chain partners of your core portfolio.
*   **Recursive Crawling**: Configurable depth (Default: 3 hops) ensures the system finds hidden relationships through "friend-of-a-friend" networks.
*   **Graph Visualization**: Interactive "Network Graph" in the UI visualizes these discovered connections.

### ⚙️ 3. Execution Modes
The application supports multiple execution modes to suit your development or trading needs:
*   **Production Mode (`--production`)**: Strict live data enforcement. No mock data. intended for actual decision making.
*   **Live Mode (`--live`)**: Prioritizes API data but may fallback if limits are reached.
*   **Synthetic Mode (`--synthetic`)**: Uses local database or synthetic patterns. Ideal for UI testing and development without burning API credits.

### 🛡️ 4. Portfolio & Risk Management
*   **Multi-Portfolio Architecture**: Manage distinct strategies (e.g., "Long Term Growth", "Speculative", "Income").
*   **Risk Dashboard**: Visualizes volatility and VaR (Value at Risk) to ensure you aren't overexposed.
*   **Holdings Analysis**: Aggregate performance tracking and safety scoring based on historical volatility.

---

## 🏗 System Architecture

The project follows a **Domain-Driven Design (DDD)** approach, ensuring separation of concerns between data fetching, business logic, and presentation.

```text
ai_stock_analytics/
├── data/                   # Persistent storage (DuckDB / Parquet)
├── src/
│   ├── analytics/          # The "Brain" of the system
│   │   ├── fusion.py       # Pressure Score algorithms
│   │   ├── gemini_analyst.py # AI Agent integration
│   │   └── risk.py         # VaR/CVaR calculations
│   ├── data/               # Data Infrastructure
│   │   ├── ingestion.py    # Robust fetching with Fallback logic
│   │   └── providers.py    # AlphaVantage / YFinance implementations
│   ├── models/             # Core Entities (Portfolio, Position)
│   ├── ui/                 # Streamlit Frontend
│   │   ├── app.py          # Main entry point
│   │   └── views/          # Modular view components
│   └── utils/              # Configuration & Helpers
└── tests/                  # Integrity verification
```

### Robust Data Pipeline
The system implements a **Resilient Provider Pattern**:
1.  **Primary**: Alpha Vantage (Institutional quality data).
2.  **Fallback**: Yahoo Finance (Automatic failover if API keys missing or limits exhausted).
3.  **Caching**: Aggressive local caching (file-based) prevents API throttling and ensures instant UI loads.

---

## 🛠 Installation & Setup

### Prerequisites
*   **Python 3.10+** (Recommended)
*   **Google Gemini API Key** (Required for Deep Research)
*   **Alpha Vantage API Key** (Recommended for best data quality)

### 1. Clone & Install
```bash
git clone https://github.com/hylle9/ai_stock_analytics.git
cd ai_stock_analytics

# Create Virtual Environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```bash
touch .env
```

Add your configuration (see `src/utils/config.py` for all options):
```ini
# --- API KEYS ---
# Required for AI Features
GOOGLE_API_KEY=your_gemini_key_here

# Recommended for Best Data Quality
ALPHA_VANTAGE_API_KEY=your_av_key_here

# --- APP CONFIGURATION ---
# Feature Flags
ENABLE_REAL_SENTIMENT=True
USE_MOCK_DATA=False

# Data Settings
DATA_CACHE_DIR=data
MAX_RETRIES=3
```

### 3. Run the Application
The application can be run in different modes depending on your intent.

**Production Mode (Recommended for Usage):**
```bash
# Terminal 1: Run the UI
streamlit run src/ui/app.py -- --production

# Terminal 2: Run the Data Collect Server (Background Updates)
python -m src.dcs.main
```
*Enforces strict live data usage and disables development shortcuts.*

**Standard/Live Mode:**
```bash
streamlit run src/ui/app.py -- --live
```

**Development/Synthetic Mode:**
```bash
streamlit run src/ui/app.py -- --synthetic
```

*Access the dashboard at `http://localhost:8501`*

---

## 📖 Usage Guide

### The Daily Workflow
1.  **Dashboard Scan**: Start with the **"Rising Stocks"** or **"Favorites"** panels. Look for the "Beating Market" badge.
2.  **Deep Dive Analysis**: Click "Analysis" on any stock card.
    *   Review the **P/E Ratio** and **Signal Components**.
    *   Check specific metrics like **RSI** and **News Sentiment**.
3.  **AI Consultation**: If a stock looks interesting:
    *   Scroll down to "First-Class AI Insight".
    *   Click **"Run Deep Research"**.
    *   Read the generated report for a second opinion.
4.  **Portfolio Action**: Add the stock to a "Watchlist" or "Live" portfolio.
5.  **Risk Check**: Visit the **Risk Dashboard** to see how this new position affects your overall portfolio volatility.

---

## 📄 License
This project is open-source and available under the MIT License.
