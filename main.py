import os
import sys
import subprocess

def main():
    """
    Entry point for AI Stock Analytics.
    Runs the Streamlit dashboard.
    """
    print("Starting AI Stock Analytics Dashboard...")
    
    # Get the path to the streamlit app
    app_path = os.path.join(os.path.dirname(__file__), "src", "ui", "app.py")
    
    # Run streamlit
    # We use sys.executable to ensure we use the same python interpreter (e.g. venv)
    cmd = [sys.executable, "-m", "streamlit", "run", app_path]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopping application...")
    except Exception as e:
        print(f"Error running application: {e}")

if __name__ == "__main__":
    main()
