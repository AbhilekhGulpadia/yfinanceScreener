import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from extensions import db, socketio
from models import OHLCV
from nifty500 import get_all_symbols, get_symbol_without_suffix
# from services.kite_client import kite_client

# Set up logging
logger = logging.getLogger(__name__)

def download_5year_data():
    """
    Download 5 years of daily OHLCV data for all stocks in symbols.csv using yfinance.
    Reads symbol list from services/symbols.csv to ensure all 502+ stocks are downloaded.
    """
    import os
    import csv
    import yfinance as yf
    
    # Read symbols from symbols.csv file
    symbols_file = os.path.join(os.path.dirname(__file__), 'symbols.csv')
    symbols = []
    
    try:
        with open(symbols_file, 'r') as f:
            reader = csv.DictReader(f)
            # Extract Symbol column and strip .NS suffix if present, then re-add it
            for row in reader:
                symbol = row['Symbol'].strip()
                if not symbol.endswith('.NS'):
                    symbol = f"{symbol}.NS"
                symbols.append(symbol)
        
        # Remove duplicates while preserving order
        seen = set()
        symbols = [s for s in symbols if not (s in seen or seen.add(s))]
        
        logger.info(f"Loaded {len(symbols)} unique symbols from symbols.csv")
    except Exception as e:
        logger.error(f"Error reading symbols.csv: {str(e)}")
        # Fallback to nifty500 module if file read fails
        logger.warning("Falling back to get_all_symbols()")
        symbols = get_all_symbols()
    
    total = len(symbols)
    logger.info(f"Starting 5-year data download for {total} stocks using yfinance...")
    
    socketio.emit('refresh_progress', {
        'current': 0,
        'total': total,
        'progress': 0,
        'status': 'started',
        'message': f'Starting 5-year data download for {total} stocks from symbols.csv...'
    })
    
    # Clear existing data
    try:
        logger.info("Clearing existing OHLCV data...")
        OHLCV.query.delete()
        db.session.commit()
        logger.info("Existing data cleared")
    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}")
        db.session.rollback()
    
    # Download 5 years of data
    # We loop through symbols to provide granular progress updates
    success_count = 0
    total_records = 0
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            # Fetch 5 years of daily data using yfinance
            # yfinance expects symbols like 'RELIANCE.NS'
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5y", interval="1d")
            
            if not df.empty:
                records_added = 0
                for index, row in df.iterrows():
                    # Skip if close price is 0 or NaN (market closed or error)
                    if pd.isna(row['Close']) or float(row['Close']) == 0:
                        continue
                    
                    # index is the Timestamp
                    timestamp = index
                    if hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                    
                    # Convert to UTC or strip timezone for storage
                    # Our DB likely expects naive datetime or UTC
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.astimezone(timezone.utc)
                        timestamp = timestamp.replace(tzinfo=None)
                    
                    ohlcv = OHLCV(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=int(row['Volume'])
                    )
                    db.session.add(ohlcv)
                    records_added += 1
                
                if records_added > 0:
                    db.session.commit()
                    total_records += records_added
                    success_count += 1
                    logger.info(f"Added {records_added} records for {symbol}")
            
            # Emit progress
            progress = int((idx / total) * 100)
            socketio.emit('refresh_progress', {
                'current': idx,
                'total': total,
                'progress': progress,
                'symbol': symbol,
                'records_added': total_records,
                'status': 'processing'
            })
            
        except Exception as e:
            logger.error(f"Error downloading data for {symbol}: {str(e)}")
            db.session.rollback()
            continue
    
    socketio.emit('refresh_progress', {
        'current': total,
        'total': total,
        'progress': 100,
        'status': 'completed',
        'message': f'Download completed! {success_count}/{total} stocks processed. Total records: {total_records}'
    })
    
    logger.info(f"5-year data download completed. {success_count}/{total} stocks, {total_records} records added.")

# Keep these for backward compatibility but redirect to new function
def fetch_ohlcv_data():
    """Legacy function - redirects to download_5year_data"""
    download_5year_data()

def refresh_latest_data():
    """Legacy function - redirects to download_5year_data"""
    download_5year_data()

def fetch_historical_ohlcv(symbol, period='5y', interval='1d', emit_progress=False, current=0, total=0):
    """Legacy function - not used anymore"""
    pass

def initialize_all_historical_data():
    """Legacy function - redirects to download_5year_data"""
    download_5year_data()
