import logging
import pandas as pd
import gc
from datetime import datetime, timezone, timedelta
from extensions import db, socketio
from models import OHLCV
from nifty500 import get_all_symbols, get_symbol_without_suffix

# Set up logging
logger = logging.getLogger(__name__)

# Batch size for processing stocks
BATCH_SIZE = 25


def download_5year_data():
    """
    Download 5 years of daily OHLCV data for all stocks in symbols.csv using yfinance.
    Optimized with bulk inserts and batch processing for reduced memory usage.
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
    
    success_count = 0
    total_records = 0
    
    # Process stocks in batches to control memory
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch_symbols = symbols[batch_start:batch_end]
        
        for idx, symbol in enumerate(batch_symbols, batch_start + 1):
            try:
                # Fetch 5 years of daily data using yfinance
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5y", interval="1d")
                
                if not df.empty:
                    # Reset index to get timestamp as column
                    df = df.reset_index()
                    
                    # Filter out rows with 0 or NaN close price
                    df = df[df['Close'].notna() & (df['Close'] != 0)]
                    
                    if len(df) > 0:
                        # Prepare bulk insert data
                        records = []
                        for _, row in df.iterrows():
                            timestamp = row['Date']
                            if hasattr(timestamp, 'to_pydatetime'):
                                timestamp = timestamp.to_pydatetime()
                            
                            # Convert to UTC and strip timezone
                            if timestamp.tzinfo is not None:
                                timestamp = timestamp.astimezone(timezone.utc)
                                timestamp = timestamp.replace(tzinfo=None)
                            
                            records.append({
                                'symbol': symbol,
                                'timestamp': timestamp,
                                'open': float(row['Open']),
                                'high': float(row['High']),
                                'low': float(row['Low']),
                                'close': float(row['Close']),
                                'volume': int(row['Volume'])
                            })
                        
                        # Bulk insert all records for this symbol
                        if records:
                            db.session.bulk_insert_mappings(OHLCV, records)
                            db.session.commit()
                            total_records += len(records)
                            success_count += 1
                            logger.info(f"Added {len(records)} records for {symbol}")
                        
                        # Clean up DataFrame
                        del df
                        del records
                
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
        
        # Force garbage collection after each batch
        gc.collect()
        logger.info(f"Completed batch {batch_start + 1}-{batch_end} of {total}")
    
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
