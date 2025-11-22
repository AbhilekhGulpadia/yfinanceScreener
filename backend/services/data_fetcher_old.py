import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from extensions import db, socketio
from models import Stock, OHLCV
from nifty500 import get_all_symbols, get_symbol_without_suffix
from services.kite_client import kite_client

# Set up logging
logger = logging.getLogger(__name__)

def get_kite_interval(interval):
    """Map app interval to Kite interval"""
    mapping = {
        '1m': 'minute',
        '3m': '3minute',
        '5m': '5minute',
        '10m': '10minute',
        '15m': '15minute',
        '30m': '30minute',
        '60m': '60minute',
        '1h': '60minute',
        '1d': 'day'
    }
    return mapping.get(interval, 'day')

def fetch_ohlcv_data():
    """Fetch OHLCV data for all Nifty 500 stocks from Kite Connect"""
    # Assumes running in app context
    symbols = get_all_symbols()
    logger.info(f"Starting OHLCV data fetch for {len(symbols)} stocks...")
    
    success_count = 0
    error_count = 0
    batch_size = 10
    batch_count = 0
    
    # Fetch for last 2 days
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5) # Go back 5 days to handle weekends/holidays
    
    for symbol in symbols:
        try:
            # Kite symbol format (remove .NS)
            kite_symbol = get_symbol_without_suffix(symbol)
            
            df = kite_client.fetch_historical_data(
                kite_symbol, 
                from_date, 
                to_date, 
                interval='15minute'
            )
            
            if df.empty:
                logger.warning(f"No data available for {symbol}")
                error_count += 1
                continue
            
            # Get the latest data point
            latest_data = df.iloc[-1]
            # Kite returns timezone aware datetime usually (IST)
            # Ensure timestamp is converted to UTC for DB consistency
            timestamp = latest_data['timestamp']
            if pd.isna(timestamp):
                continue
                
            if hasattr(timestamp, 'to_pydatetime'):
                timestamp = timestamp.to_pydatetime()
            
            # Convert to UTC if it has timezone info
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(timezone.utc)
            else:
                # If naive, assume it's already UTC or handle as needed. 
                # Kite usually sends IST. If it's naive, it might be local time.
                # For safety, let's assume naive means we need to be careful, 
                # but usually pandas/kite gives tz-aware.
                pass
            
            # Make it naive UTC for SQLite if needed, or keep tz-aware if SQLAlchemy handles it.
            # Best practice for SQLite: store as naive UTC.
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
            
            # Check if this data point already exists
            existing = OHLCV.query.filter_by(
                symbol=symbol,
                timestamp=timestamp
            ).first()
            
            if existing:
                # Update existing record
                existing.open = float(latest_data['open'])
                existing.high = float(latest_data['high'])
                existing.low = float(latest_data['low'])
                existing.close = float(latest_data['close'])
                existing.volume = int(latest_data['volume'])
                existing.last_updated = datetime.now(timezone.utc)
            else:
                # Create new record
                ohlcv = OHLCV(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=float(latest_data['open']),
                    high=float(latest_data['high']),
                    low=float(latest_data['low']),
                    close=float(latest_data['close']),
                    volume=int(latest_data['volume'])
                )
                db.session.add(ohlcv)
            
            # Update stock price in stocks table if exists
            stock = Stock.query.filter_by(symbol=kite_symbol).first()
            if stock:
                stock.current_price = float(latest_data['close'])
            
            success_count += 1
            batch_count += 1
            
            # Commit in batches
            if batch_count >= batch_size:
                try:
                    db.session.commit()
                    logger.debug(f"Committed batch of {batch_count} stocks")
                    batch_count = 0
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error committing batch: {str(e)}")
                    batch_count = 0
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            error_count += 1
            db.session.rollback()
            continue
    
    # Commit remaining
    if batch_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error committing final batch: {str(e)}")
    
    logger.info(f"OHLCV data fetch completed. Success: {success_count}, Errors: {error_count}")

def fetch_historical_ohlcv(symbol, period='5y', interval='15m', emit_progress=False, current=0, total=0):
    """Fetch historical OHLCV data for a specific stock"""
    # Assumes running in app context
    try:
        # Calculate dates based on period
        to_date = datetime.now()
        if period == '5y':
            from_date = to_date - timedelta(days=5*365)
        elif period == '1y':
            from_date = to_date - timedelta(days=365)
        elif period == '1mo':
            from_date = to_date - timedelta(days=30)
        else:
            from_date = to_date - timedelta(days=365) # Default
            
        kite_interval = get_kite_interval(interval)
        kite_symbol = get_symbol_without_suffix(symbol)
        
        # Kite has limits on duration for minute data (e.g. 60 days for 1m). 
        # For 15m it's likely longer but we might need to chunk requests if 5y is too long.
        # For now, let's try fetching all, or maybe chunk by year if it fails.
        # Kite API limit for candle data is 2000 candles per call usually.
        # 5 years of 15m data is a lot. 
        # 5 * 250 * 25 = 31250 candles. We definitely need to chunk.
        
        # Chunking logic: 100 days per chunk to be safe
        chunk_size_days = 100
        current_from = from_date
        all_records_count = 0
        
        while current_from < to_date:
            current_to = min(current_from + timedelta(days=chunk_size_days), to_date)
            
            try:
                df = kite_client.fetch_historical_data(
                    kite_symbol, 
                    current_from, 
                    current_to, 
                    kite_interval
                )
                
                if not df.empty:
                    batch_count = 0
                    for _, row in df.iterrows():
                        try:
                            timestamp = row['timestamp']
                            if hasattr(timestamp, 'to_pydatetime'):
                                timestamp = timestamp.to_pydatetime()
                            
                            # Convert to UTC
                            if timestamp.tzinfo is not None:
                                timestamp = timestamp.astimezone(timezone.utc)
                            
                            # Make naive UTC
                            if timestamp.tzinfo is not None:
                                timestamp = timestamp.replace(tzinfo=None)
                                
                            existing = OHLCV.query.filter_by(
                                symbol=symbol,
                                timestamp=timestamp
                            ).first()
                            
                            if not existing:
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
                                all_records_count += 1
                                batch_count += 1
                        except Exception:
                            continue
                    
                    if batch_count > 0:
                        db.session.commit()
                        
            except Exception as e:
                logger.error(f"Error fetching chunk {current_from} to {current_to}: {str(e)}")
                # Continue to next chunk
            
            current_from = current_to
            
        logger.info(f"Added {all_records_count} historical records for {symbol}")
        
        if emit_progress and total > 0:
            progress = int((current / total) * 100)
            socketio.emit('initialization_progress', {
                'current': current,
                'total': total,
                'progress': progress,
                'symbol': symbol,
                'records_added': all_records_count,
                'status': 'processing'
            })
        
        return all_records_count
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return 0

def initialize_all_historical_data():
    """Initialize 5 years of historical data for all stocks with progress tracking"""
    symbols = get_all_symbols()
    total = len(symbols)
    logger.info(f"Starting initialization of 5-year historical data for {total} stocks...")
    
    socketio.emit('initialization_progress', {
        'current': 0,
        'total': total,
        'progress': 0,
        'status': 'started',
        'message': f'Starting initialization for {total} stocks...'
    })
    
    success_count = 0
    total_records = 0
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            records = fetch_historical_ohlcv(
                symbol, 
                period='5y', 
                interval='15m',
                emit_progress=True,
                current=idx,
                total=total
            )
            total_records += records
            success_count += 1
            
        except Exception as e:
            logger.error(f"Error initializing {symbol}: {str(e)}")
            socketio.emit('initialization_progress', {
                'current': idx,
                'total': total,
                'progress': int((idx / total) * 100),
                'symbol': symbol,
                'status': 'error',
                'error': str(e)
            })
    
    socketio.emit('initialization_progress', {
        'current': total,
        'total': total,
        'progress': 100,
        'status': 'completed',
        'message': f'Completed! {success_count}/{total} stocks initialized with {total_records} records.',
        'success_count': success_count,
        'total_records': total_records
    })
    
    logger.info(f"Historical data initialization completed. {success_count}/{total} stocks, {total_records} records added.")

def refresh_latest_data():
    """Refresh latest OHLCV data for all stocks and cleanup old records"""
    symbols = get_all_symbols()
    total = len(symbols)
    logger.info(f"Starting refresh of latest data for {total} stocks...")
    
    socketio.emit('refresh_progress', {
        'current': 0,
        'total': total,
        'progress': 0,
        'status': 'started',
        'message': f'Starting data refresh for {total} stocks...'
    })
    
    success_count = 0
    cleanup_count = 0
    five_years_ago = datetime.now(timezone.utc) - timedelta(days=5*365)
    
    # Fetch for last 5 days to be safe
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            kite_symbol = get_symbol_without_suffix(symbol)
            
            df = kite_client.fetch_historical_data(
                kite_symbol, 
                from_date, 
                to_date, 
                interval='15minute'
            )
            
            records_added = 0
            if not df.empty:
                for _, row in df.iterrows():
                    timestamp = row['timestamp']
                    if hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                    
                    # Convert to UTC
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.astimezone(timezone.utc)
                    
                    # Make naive UTC
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.replace(tzinfo=None)
                        
                    existing = OHLCV.query.filter_by(
                        symbol=symbol,
                        timestamp=timestamp
                    ).first()
                    
                    if not existing:
                        new_ohlcv = OHLCV(
                            symbol=symbol,
                            timestamp=timestamp,
                            open=float(row['open']),
                            high=float(row['high']),
                            low=float(row['low']),
                            close=float(row['close']),
                            volume=int(row['volume'])
                        )
                        db.session.add(new_ohlcv)
                        records_added += 1
                
                # Cleanup old records
                old_records = OHLCV.query.filter(
                    OHLCV.symbol == symbol,
                    OHLCV.timestamp < five_years_ago
                ).all()
                
                for record in old_records:
                    db.session.delete(record)
                    cleanup_count += 1
                
                db.session.commit()
                success_count += 1
                
                socketio.emit('refresh_progress', {
                    'current': idx,
                    'total': total,
                    'progress': int((idx / total) * 100),
                    'symbol': symbol,
                    'records_added': records_added,
                    'records_cleaned': len(old_records),
                    'status': 'processing'
                })
                
        except Exception as e:
            logger.error(f"Error refreshing data for {symbol}: {str(e)}")
            db.session.rollback()
            continue
    
    socketio.emit('refresh_progress', {
        'current': total,
        'total': total,
        'progress': 100,
        'status': 'completed',
        'message': f'Refresh completed! {success_count}/{total} stocks updated. {cleanup_count} old records removed.'
    })
    
    logger.info(f"Data refresh completed. {success_count}/{total} stocks updated. {cleanup_count} old records removed.")
