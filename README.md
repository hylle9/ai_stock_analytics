# AI Stock Analytics (ASA)

<div align="center">
  <h3>Institutional-Grade Market Intelligence for Everyone</h3>
  <p>Multi-Modal Analysis • Deep AI Research • Portfolio Management • Risk Analytics</p>
</div>

---

## 🚀 Project Overview

**AI Stock Analytics (ASA)** is an advanced market analysis platform composed of a "Fusion Engine" that combines traditional technical indicators with alternative data streams and Large Language Model (LLM) reasoning.

Unlike simple chart wrappers, **ASA** treats the market as a complex system, analyzing:
1.  **Price Action:** Technical momentum and trend stability.
2.  **Market Psychology:** Social sentiment and web search volume intensity.
3.  **Fundamental Valuation:** P/E ratios and market cap context.
4.  **Macro Context:** Returns relative to the broader market (Alpha).

The system aggregates these signals into a unified **"Pressure Score"** (0-100), helping you identify high-probability opportunities where retail enthusiasm meets technical strength.

⚠️ **Status**: Pre-Alpha / Active Development.

---

## ✨ Key Features

### 🧠 1. Deep Research Agent (Gemini Powered)
Go beyond simple numbers with our integrated AI Analyst.
*   **Deep Dives**: On-demand generation of comprehensive research reports using **Google Gemini Pro**.
*   **Smart Caching**: "Weekly Research" reports are cached for 7 days to prevent analysis fatigue and API rate limits.
*   **Multi-Modal Context**: The AI sees what you see—analysis is grounded in the exact RSI, Sentiment, and Volatility metrics currently displayed.

### ⚡ 2. The "Fusion Engine" & Pressure Score
Our proprietary scoring system quantifies the directional energy of a stock:
*   **Price Trend (30%)**: Normalized momentum (RSI, ROC, SMA Deviations).
*   **Volatility Energy (20%)**: Measures latent kinetic energy (Bollinger Band compression).
*   **Social Sentiment (25%)**: Real-time news sentiment and social signal proxy.
*   **Web Attention (25%)**: Viral intensity tracking (Search/Social volume).

**Pressure Score Interpretation**:
*   🟢 **> 70**: High Momentum (Strong Buy zone if not overextended).
*   🟡 **40-70**: Neutral / Consolidation.
*   🔴 **< 40**: Weakness (Sell / Avoid zone).

### 📊 3. Advanced Dashboarding
*   **Market Beat Alpha**: Instantly see if a stock is outperforming the S&P 500 (displayed as "🚀 Beating Market" or "📉 Losing to Market").
*   **Valuation Context**: P/E Ratios integrated directly into stock cards.
*   **Activity Tracking**: "Favorites" and "Rising Stocks" lists auto-populate based on your interaction history.

### 🛡️ 4. Portfolio & Risk Management
*   **Multi-Portfolio Support**: Create distinct portfolios (e.g., "Long Term Growth", "Speculative").
*   **Risk Dashboard**: Visualize the volatility and VaR (Value at Risk) of your holdings vs. the broader universe.
*   **Holdings Analysis**: Aggregate performance tracking and safety scoring.

---

## 🏗 System Architecture

The project follows a Domain-Driven Design (DDD) with a clean separation between data ingestion, analytical logic, and presentation.

```text
ai_stock_analytics/
├── data/                   # Persistent storage (Parquet/JSON caches)
├── src/
│   ├── analytics/          # The "Brain" of the system
│   │   ├── fusion.py       # Pressure Score algorithms
│   │   ├── gemini_analyst.py # AI Agent integration
│   │   ├── risk.py         # VaR/CVaR calculations
│   │   └── sentiment.py    # NLP engines
│   ├── data/               # Data Infrastructure
│   │   ├── ingestion.py    # Robust fetching with Fallback logic
│   │   └── providers.py    # AlphaVantage / YFinance implementations
│   ├── models/             # Core Entities (Portfolio, Position)
│   └── ui/                 # Streamlit Frontend
│       ├── app.py          # Main entry point
│       └── views/          # Modular view components
└── tests/                  # Integrity verification
```

### Robust Data Pipeline
The system uses a **Resilient Provider Pattern**:
1.  **Primary**: Alpha Vantage (Institutional quality data).
2.  **Fallback**: Yahoo Finance (Automatic failover if API keys missing/exhausted).
3.  **Caching**: Aggressive local caching prevents API throttling and ensures instant UI loads.

---

## 🛠 Installation & Setup

### Prerequisites
*   **Python 3.10+** (Recommended)
*   **Google Gemini API Key** (for Deep Research)
*   **Alpha Vantage API Key** (Optional, for premium data)

### 1. Clone & Install
```bash
git clone https://github.com/hylle9/ai_stock_analytics.git
cd ai_stock_analytics

# Create Virtual Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```bash
touch .env
```

Add your keys:
```ini
# Required for AI Features
GOOGLE_API_KEY=your_gemini_key_here

# Recommended for Best Data Quality
ALPHA_VANTAGE_API_KEY=your_av_key_here

# App Settings
DATA_CACHE_DIR=data
```

### 3. Run the Application
```bash
# Run using the startup script wrapper (recommended)
python main.py

# OR directly via Streamlit
streamlit run src/ui/app.py
```
*Access the dashboard at `http://localhost:8501`*

---

## 📖 Usage Guide

### The Workflow
1.  **Dashboard**: Start here. Check your **"Rising Stocks"** to see what's moving today. Look for green "Beating Market" badges.
2.  **Analysis**: Click "Analysis" on any card.
    *   Review the **P/E Ratio** and **Signal Components**.
    *   Check specific metrics like **RSI** and **News Sentiment**.
3.  **Deep Research**: If a stock looks interesting but complex:
    *   Scroll down to "First-Class AI Insight".
    *   Click **"Run Deep Research"**.
    *   Read the generated report on Strategy, Risks, and Outlook.
4.  **Portfolio**: Add the stock to your "Watchlist" or "Live" portfolio to track its risk contribution.

---

## 🔮 Roadmap

*   [x] **mvp**: Core Dashboard & Analysis
*   [x] **feat**: Gemini AI Integration (Deep Research)
*   [x] **feat**: P/E Ratios & Fundamental Data
*   [ ] **feat**: Automated "Morning Briefing" emails
*   [ ] **feat**: Docker Containerization
*   [ ] **feat**: User Authentication (Multi-tenant)

---

## 📄 License
This project is open-source and available under the MIT License.
