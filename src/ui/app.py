import streamlit as st
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ui.views.universe_view import render_universe_view
from src.ui.views.stock_view import render_stock_view
from src.ui.views.risk_view import render_risk_view
from src.ui.views.portfolio_view import render_portfolio_view

def main():
    st.set_page_config(page_title="AI Stock Lab", layout="wide")
    
    st.sidebar.title("AI Stock Lab")
    
    page = st.sidebar.radio("Navigation", ["Dashboard", "Stock Analysis", "Risk Dashboard", "Portfolio & Robo-Advisor", "Universe Management"])
    
    if page == "Dashboard":
        st.title("Market Dashboard")
        st.info("Market overview coming soon...")
    elif page == "Stock Analysis":
        render_stock_view()
    elif page == "Risk Dashboard":
        render_risk_view()
    elif page == "Portfolio & Robo-Advisor":
        render_portfolio_view()
    elif page == "Universe Management":
        render_universe_view()

if __name__ == "__main__":
    main()
