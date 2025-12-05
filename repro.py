import sys
import os

# Mimic app.py path setup
# app.py is in src/ui/app.py
# It does: sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
# We are creating this script in ai_stock_analytics/repro.py
# So we need to add ai_stock_analytics to path.
# Actually, let's just add the current directory to path if we run from ai_stock_analytics root.

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

print(f"Sys path: {sys.path}")

try:
    from src.features.technical import add_technical_features
    print("Import successful!")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
