import pandas as pd
from app import create_app
from extensions import db
from models import OHLCV
import os

def export_data():
    app = create_app()
    with app.app_context():
        print("Fetching data from database...")
        # Fetch all data using raw SQL
        # Use db.engine directly
        with db.engine.connect() as connection:
            df = pd.read_sql("SELECT * FROM ohlcv_data", connection)
        
        if df.empty:
            print("No data found in OHLCV table.")
            return
            
        print(f"Found {len(df)} records.")
        
        # Format timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['last_updated'] = pd.to_datetime(df['last_updated'])
        
        df['timestamp'] = df['timestamp'].apply(lambda x: x.replace(tzinfo=None) if pd.notnull(x) else None)
        df['last_updated'] = df['last_updated'].apply(lambda x: x.replace(tzinfo=None) if pd.notnull(x) else None)
        
        output_file = 'ohlcv_data_export.xlsx'
        print(f"Writing to {output_file}...")
        df.to_excel(output_file, index=False)
        print(f"Export completed successfully! File saved as {os.path.abspath(output_file)}")

if __name__ == '__main__':
    export_data()
