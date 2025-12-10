#!/bin/bash
# Activate virtual environment
source venv/bin/activate

# Run DCS
echo "🚀 Starting Data Collect Server (DCS)..."
python -m src.dcs.main
