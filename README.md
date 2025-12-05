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

### 3. AI-Powered Forecasting
Integrated time-series forecasting using **Facebook Prophet**:
- Decomposes price action into trends, weekly seasonality, and yearly seasonality.
- Provides **1-Day** and **5-Day** return forecasts with confidence intervals.
- Visualizes "uncertainty cones" to help users gaze risk.

### 4. Interactive Dashboard
Built with **Streamlit** and **Plotly**, the UI offers:
- **Universe View**: A high-level heatmap and ranking table to spot top movers and RPS outliers.
- **Stock Detail View**: Deep-dive analysis for individual tickers, featuring:
  - Interactive candlestick charts with forecast overlays.
  - Dual-axis charts comparing Price vs. Retail Participation.
  - Tabbed views for Technicals, Behavioral Analysis, and News.

---

## 🏗 System Architecture

The project follows a modular, domain-driven structure to ensure scalability and separation of concerns.

```text
ai_stock_analyics/
├── main.py                 # Application Entry Point
├── data/                   # Local storage for cached market data (Parquet)
├── src/
│   ├── analytics/          # Core Logic & Math
│   │   ├── fusion.py       # Pressure Score calculation
│   │   ├── microstructure.py # RPS & Liquidity metrics
│   │   ├── technical.py    # TA Lib wrappers (RSI, MACD, BB)
│   │   ├── risk.py         # Volatility & Risk sizing
│   │   └── sentiment.py    # NLP & Sentiment analysis stub
│   ├── data/               # Data Layer
│   │   ├── ingestion.py    # DataFetcher class (yfinance, caching)
│   │   └── universe.py     # Ticker universe definitions
│   ├── features/           # Feature Engineering (Legacy/Transition)
│   ├── models/             # AI/ML Models
│   │   └── forecaster.py   # Prophet Forecasting Logic
│   └── ui/                 # Presentation Layer
│       ├── app.py          # Streamlit Main Layout
│       ├── dashboard.py    # Landing Page / Market Overview
│       └── stock_view.py   # Detailed Ticker Analysis View
```

### Key Components
- **`src/data/ingestion.py`**: Smart caching layer. It fetches data from `yfinance`, saves it to `data/raw/*.parquet`, and reloads from disk if the data is less than 24 hours old. This significantly speeds up development and reduces API rate limits.
- **`src/analytics/fusion.py`**: Contains the proprietary logic for weighting and normalizing the multi-modal signals.

---

## 🛠 Installation & Setup

### Prerequisites
- Python 3.9+
- pip (Python Package Manager)

### Quick Start

1. **Clone the Repository**
   ```bash
   git clone <repo-url>
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
   *Alternatively, you can run directly with streamlit:*
   ```bash
   streamlit run src/ui/app.py
   ```

---

## 📖 Usage Guide

### 1. Market Overview
Upon launching, you will see the **Market Overview**.
- **Top Retail Movers**: A table showing stocks with the highest "RPS" (Retail Participation Score). Use this to find stocks that are currently "in play."
- **Progress Bar**: Indicates the loading status of the analysis pipeline.

### 2. Analyzing a Stock
1. Go to the sidebar.
2. Enter a valid US Ticker Symbol (e.g., `AAPL`, `NVDA`, `GME`).
3. Click **"Analyze"**.
4. The main view will update with:
   - **Header Metrics**: Current Price, RPS Score, Forecasted Return, and Confidence.
   - **Tabs**:
     - *Price & Forecast*: Visualizes the Prophet model's prediction.
     - *Behavioral*: Shows the relationship between Volume and the RPS score.
     - *Technical*: Standard indicators like RSI and ATR.

---

## 🔮 Roadmap

- **Phase 2: True Multi-Modal (In Progress)**
  - Replace synthetic sentiment with real Twitter/X & Reddit NLP analysis.
  - Integrate live Google Trends API for real-time attention scoring.
  - Refine Fusion Engine weights using a genetic algorithm or regression model.

- **Phase 3: Portfolio & Robo-Advisor**
  - Add "Portfolio Optimization" module using Mean-Variance Optimization (MVO).
  - Implement "Robo-Advisor" chat interface for natural language queries (e.g., *"Why is my portfolio down today?"*).

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
