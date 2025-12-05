# AI Stock Analytics (ASA)

## 🚀 Project Overview

**AI Stock Analytics (ASA)** is an advanced, multi-modal market analysis platform designed to democratize institutional-grade financial insights. By combining traditional technical analysis with cutting-edge alternative data (web attention, social sentiment) and microstructure anomalies, ASA provides a holistic view of market dynamics that goes beyond simple price charts.

The core philosophy of ASA is **Data Fusion**: leveraging multiple disparate signal sources to calculate a unified **"Pressure Score"** that quantifies the directional intensity of a stock. This allows traders and analysts to identify high-probability opportunities where price action, market sentiment, and retail behavior align.

⚠️ **Status**: Pre-Alpha / MVP Phase. The current implementation focuses on the foundational architecture, data ingestion pipelines, and core visualization engine.

---

## ✨ Key Features

### 1. Multi-Modal "Fusion Engine"
The heart of the system is the `FusionEngine`, which aggregates signals from four distinct dimensions into a single actionable metric (0-100):
- **Price Trend (30%)**: Normalized momentum derived from technical indicators (RSI, ROC).
- **Volatility Energy (20%)**: Market "temperature" based on volatility rankings; treats high volatility as potential kinetic energy for moves.
- **Social Sentiment (25%)**: (Synthetic in MVP) Measures the qualitative mood of the market.
- **Web Attention (25%)**: (Google Trends / Synthetic) Measures the quantitative volume of interest.

**The output is a "Pressure Score"**:
- **> 50**: Bullish Pressure (Buying intensity)
- **< 50**: Bearish Pressure (Selling intensity)
- **50**: Neutral Equilibrium

### 2. Retail Participation Signal (RPS) Proxy
A novel metric designed to detect "meme stock" like activity or retail frenzies.
- **Logic**: Detects the confluence of **Abnormal Volume** (Z-Score > 2) and **Abnormal Volatility** without significant institutional news flow.
- **Goal**: To flag when price moves are being driven by retail flows rather than fundamental repricing.
- *Note: Currently implemented as a heuristic proxy in `src/analytics/microstructure.py`.*

### 3. Multi-Portfolio Management
Create and manage multiple distinct portfolios (e.g., "Safe Growth" vs "High Risk").
- **States**: Portfolios can be set to **Live**, **Paused**, or **Archived**.
- **Robo-Advisor Integration**: Each active portfolio can receive tailored allocation recommendations.
- **Persistence**: Session-based storage allows for rapid prototyping and testing of different strategies.

### 4. Advanced Risk Dashboard
Analyze not just the market, but your specific exposures.
- **Source Selection**: Toggle between analyzing the entire **Universe** or a specific **Portfolio**.
- **Metrics**: Real-time calculation of **Value at Risk (VaR)**, **Conditional VaR (Expected Shortfall)**, and Annualized Volatility.
- **Visuals**: Scatter plots (Risk vs Volatility) to identify outliers.

### 5. Resilient Data Architecture
A robust "provider" pattern ensures the app never breaks due to missing API keys.
- **Primary**: Alpha Vantage (for institutional-grade data).
- **Fallback**: Yahoo Finance (yfinance) automatically takes over if API keys are missing.
- **Smart Caching**: Local parquet caching prevents rate-limiting and speeds up repeated analysis.

---

## 🏗 System Architecture

The project follows a modular, domain-driven structure to ensure scalability and separation of concerns.

```text
ai_stock_analytics/
├── main.py                 # Application Entry Point
├── data/                   # Local storage for cached market data (Parquet)
├── src/
│   ├── analytics/          # Core Logic & Math
│   │   ├── risk.py         # VaR, CVaR, & Volatility Metrics
│   │   ├── fusion.py       # Pressure Score calculation
│   │   └── technical.py    # TA indicators
│   ├── data/               # Data Layer
│   │   ├── providers.py    # Data Provider Strategy Pattern (AlphaVantage/YFinance)
│   │   ├── ingestion.py    # DataFetcher & Caching
│   │   └── universe.py     # Ticker universe definitions
│   ├── models/             # Domain Models
│   │   ├── portfolio.py    # Portfolio & PortfolioManager Logic
│   │   └── decision.py     # Robo-Advisor Recommender
│   └── ui/                 # Presentation Layer
│       ├── app.py          # Streamlit Main Layout
│       ├── views/          # Modular UI Views
│       │   ├── portfolio_view.py
│       │   ├── risk_view.py
│       │   └── stock_view.py
└── tests/                  # Unit & Integration Tests
```

---

## 🛠 Installation & Setup

### Prerequisites
- Python 3.9+
- pip (Python Package Manager)

### Quick Start

1. **Clone the Repository**
   ```bash
   git clone https://github.com/hylle9/ai_stock_analytics.git
   cd ai_stock_analytics
   ```

2. **Create a Virtual Environment**
   It is highly recommended to use a virtual environment.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**
   ```bash
   python main.py
   ```
   *The app will launch at http://localhost:8501*

---

## 📖 Usage Guide

### 1. Market & Risk Overview
- Check the **Risk Dashboard** to see the volatility profile of the "Big Tech" universe.
- Toggle top "Source" to "Portfolio" to see how your personal holdings compare.

### 2. Managing Portfolios
1. Navigate to **Portfolio & Robo-Advisor**.
2. **Create**: Open the sidebar expander to name a new portfolio.
3. **Status**: Use the dropdown to set it to "Live" or "Paused".
4. **Trade**: Add tickers (e.g., `NVDA`, `TSLA`) and quantities.
5. **Analyze**: Switch back to the Risk Dashboard to see your portfolio's metrics.

### 3. Detailed Analysis
- Use **Stock Analysis** to deep-dive into specific tickers with Multi-Modal signals and Price Forecasting.

---

## 🔮 Roadmap

- **Phase 4: Optimization Engine**
  - Implement full Mean-Variance Optimization (MVO) with user-selectable constraints.
  - Integration with brokerage APIs for one-click trade execution.

- **Phase 5: LLM Integration**
  - Natural language querying of portfolio performance ("Why is my exposure to Tech so high?").

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:
1. Fork the repo.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
