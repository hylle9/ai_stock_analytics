#!/bin/bash
# Activate virtual environment
source venv/bin/activate

# Run App
echo "🚀 Starting AI Stock Analytics App (Production Mode)..."
streamlit run src/ui/app.py -- --production
