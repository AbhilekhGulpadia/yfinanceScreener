import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from extensions import db, socketio
from models import OHLCV
from nifty500 import get_all_symbols, get_symbol_without_suffix
from services.kite_client import kite_client

# Set up logging
logger = logging.getLogger(__name__)

def download_5year_data():
    """
    Download 5 years of daily OHLCV data for Nifty 500 stocks only.
    Fetches Nifty 500 symbols from Kite to ensure all symbols are valid and current.
    """
    # Get Nifty 500 symbols from Kite (only symbols that exist in both Kite and Nifty 500 list)
    logger.info("Fetching Nifty 500 symbols from Kite...")
    symbols = kite_client.get_nifty500_symbols_from_kite()
    
    # Fallback to hardcoded Nifty 500 list if Kite fetch fails
    if not symbols:
        logger.warning("Failed to fetch from Kite, falling back to hardcoded Nifty 500 list")
        from nifty500 import get_nifty500_symbols
        symbols = get_nifty500_symbols()
    
    total = len(symbols)
    logger.info(f"Starting 5-year data download for {total} Nifty 500 stocks...")
    
    socketio.emit('refresh_progress', {
        'current': 0,
        'total': total,
        'progress': 0,
        'status': 'started',
        'message': f'Starting 5-year data download for {total} Nifty 500 stocks...'
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
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5*365)
    
    success_count = 0
    total_records = 0
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            kite_symbol = get_symbol_without_suffix(symbol)
            
            # Fetch 5 years of daily data
            df = kite_client.fetch_historical_data(
                kite_symbol,
                from_date,
                to_date,
                interval='day'
            )
            
            if not df.empty:
                records_added = 0
                for _, row in df.iterrows():
                    # Skip if close price is 0 (market closed)
                    if float(row['close']) == 0:
                        continue
                    
                    timestamp = row['timestamp']
                    if hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                    
                    # Convert to UTC
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.astimezone(timezone.utc)
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.replace(tzinfo=None)
                    
                    ohlcv = OHLCV(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(row['volume'])
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
