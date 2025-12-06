import requests
import csv
import json
import io
import os

URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
OUTPUT_PATH = "src/data/sp500_seed.json"

def generate_seed():
    print(f"Fetching S&P 500 data from {URL}...")
    try:
        response = requests.get(URL)
        response.raise_for_status()
        
        # Parse CSV
        f = io.StringIO(response.text)
        reader = csv.DictReader(f)
        
        database = {}
        
        for row in reader:
            ticker = row['Symbol']
            # Data cleaning
            if not ticker or not row['GICS Sector']:
                continue
                
            database[ticker] = {
                "name": row['Security'],
                "sector": row['GICS Sector'],
                "industry": row['GICS Sub-Industry'],
                "competitors": [] # Will be populated by AI or fuzzy matching later
            }
            
        print(f"Parsed {len(database)} companies.")
        
        # Save to JSON
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(database, f, indent=4)
            
        print(f"Saved seed database to {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"Error generating seed: {e}")

if __name__ == "__main__":
    generate_seed()
