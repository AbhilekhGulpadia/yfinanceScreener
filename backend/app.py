from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from config import Config
from models import db, Stock, Portfolio, Transaction, WatchList, OHLCV
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from nifty500 import (
    get_all_symbols, get_all_stocks, get_symbol_without_suffix, 
    get_stock_by_symbol, get_stocks_by_sector, get_all_sectors,
    get_nifty50_stocks, get_nifty200_stocks, get_nifty500_stocks,
    search_stocks, get_stock_count
)
import logging
import threading

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = 'your-secret-key'
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for React frontend

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# ============= YAHOO FINANCE DATA FETCHER =============
def fetch_ohlcv_data():
    """Fetch OHLCV data for all Nifty 500 stocks from Yahoo Finance"""
    with app.app_context():
        symbols = get_all_symbols()
        logger.info(f"Starting OHLCV data fetch for {len(symbols)} stocks...")
        
        success_count = 0
        error_count = 0
        batch_size = 10  # Commit every 10 stocks to reduce lock time
        batch_count = 0
        
        for symbol in symbols:
            try:
                # Fetch data for the last 2 days (to ensure we get latest data)
                ticker = yf.Ticker(symbol)
                df = ticker.history(period='2d', interval='15m')
                
                if df.empty:
                    logger.warning(f"No data available for {symbol}")
                    error_count += 1
                    continue
                
                # Get the latest data point
                latest_data = df.iloc[-1]
                timestamp = df.index[-1].to_pydatetime()
                
                # Check if this data point already exists
                existing = OHLCV.query.filter_by(
                    symbol=symbol,
                    timestamp=timestamp
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = float(latest_data['Open'])
                    existing.high = float(latest_data['High'])
                    existing.low = float(latest_data['Low'])
                    existing.close = float(latest_data['Close'])
                    existing.volume = int(latest_data['Volume'])
                    existing.last_updated = datetime.now(timezone.utc)
                else:
                    # Create new record
                    ohlcv = OHLCV(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=float(latest_data['Open']),
                        high=float(latest_data['High']),
                        low=float(latest_data['Low']),
                        close=float(latest_data['Close']),
                        volume=int(latest_data['Volume'])
                    )
                    db.session.add(ohlcv)
                
                # Update stock price in stocks table if exists
                stock_symbol = get_symbol_without_suffix(symbol)
                stock = Stock.query.filter_by(symbol=stock_symbol).first()
                if stock:
                    stock.current_price = float(latest_data['Close'])
                
                success_count += 1
                batch_count += 1
                
                # Commit in batches to reduce lock time
                if batch_count >= batch_size:
                    try:
                        db.session.commit()
                        logger.debug(f"Committed batch of {batch_count} stocks")
                        batch_count = 0
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Error committing batch: {str(e)}")
                        # Continue with next batch
                        batch_count = 0
                
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {str(e)}")
                error_count += 1
                # Rollback any pending changes for this symbol
                db.session.rollback()
                continue
        
        # Commit any remaining records
        if batch_count > 0:
            try:
                db.session.commit()
                logger.debug(f"Committed final batch of {batch_count} stocks")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error committing final batch: {str(e)}")
        
        logger.info(f"OHLCV data fetch completed. Success: {success_count}, Errors: {error_count}")

def fetch_historical_ohlcv(symbol, period='5y', interval='15m', emit_progress=False, current=0, total=0):
    """Fetch historical OHLCV data for a specific stock (default: 5 years)"""
    with app.app_context():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No historical data available for {symbol}")
                return 0
            
            count = 0
            batch_size = 50
            batch_count = 0
            
            for timestamp, row in df.iterrows():
                try:
                    # Check if this data point already exists
                    existing = OHLCV.query.filter_by(
                        symbol=symbol,
                        timestamp=timestamp.to_pydatetime()
                    ).first()
                    
                    if not existing:
                        ohlcv = OHLCV(
                            symbol=symbol,
                            timestamp=timestamp.to_pydatetime(),
                            open=float(row['Open']),
                            high=float(row['High']),
                            low=float(row['Low']),
                            close=float(row['Close']),
                            volume=int(row['Volume'])
                        )
                        db.session.add(ohlcv)
                        count += 1
                        batch_count += 1
                        
                        # Commit in batches
                        if batch_count >= batch_size:
                            db.session.commit()
                            batch_count = 0
                            
                except Exception as e:
                    logger.error(f"Error processing row for {symbol}: {str(e)}")
                    db.session.rollback()
                    batch_count = 0
                    continue
            
            # Commit remaining records
            if batch_count > 0:
                db.session.commit()
            
            logger.info(f"Added {count} historical records for {symbol}")
            
            # Emit progress if requested
            if emit_progress and total > 0:
                progress = int((current / total) * 100)
                socketio.emit('initialization_progress', {
                    'current': current,
                    'total': total,
                    'progress': progress,
                    'symbol': symbol,
                    'records_added': count,
                    'status': 'processing'
                })
            
            return count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return 0

def initialize_all_historical_data():
    """Initialize 5 years of historical data for all stocks with progress tracking"""
    with app.app_context():
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
        
        # Emit completion
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

# Schedule the data fetch every 15 minutes
scheduler.add_job(
    func=fetch_ohlcv_data,
    trigger="interval",
    minutes=15,
    id='fetch_ohlcv_job',
    name='Fetch OHLCV data every 15 minutes',
    replace_existing=True
)

# Fetch data immediately on startup
scheduler.add_job(
    func=fetch_ohlcv_data,
    trigger='date',
    run_date=datetime.now() + timedelta(seconds=5),
    id='initial_fetch',
    name='Initial OHLCV data fetch'
)

# ============= HEALTH CHECK =============
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Backend is running'})

# ============= STOCKS ENDPOINTS =============
@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get all stocks"""
    stocks = Stock.query.all()
    return jsonify({'stocks': [stock.to_dict() for stock in stocks]})

@app.route('/api/stocks/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    """Get a specific stock by ID"""
    stock = Stock.query.get_or_404(stock_id)
    return jsonify(stock.to_dict())

@app.route('/api/stocks', methods=['POST'])
def create_stock():
    """Create a new stock"""
    data = request.get_json()
    
    # Check if stock symbol already exists
    existing = Stock.query.filter_by(symbol=data['symbol']).first()
    if existing:
        return jsonify({'error': 'Stock symbol already exists'}), 400
    
    stock = Stock(
        symbol=data['symbol'],
        name=data['name'],
        sector=data.get('sector'),
        current_price=data.get('current_price'),
        market_cap=data.get('market_cap')
    )
    
    db.session.add(stock)
    db.session.commit()
    
    return jsonify({'message': 'Stock created successfully', 'stock': stock.to_dict()}), 201

@app.route('/api/stocks/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id):
    """Update a stock"""
    stock = Stock.query.get_or_404(stock_id)
    data = request.get_json()
    
    stock.name = data.get('name', stock.name)
    stock.sector = data.get('sector', stock.sector)
    stock.current_price = data.get('current_price', stock.current_price)
    stock.market_cap = data.get('market_cap', stock.market_cap)
    
    db.session.commit()
    
    return jsonify({'message': 'Stock updated successfully', 'stock': stock.to_dict()})

@app.route('/api/stocks/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    """Delete a stock"""
    stock = Stock.query.get_or_404(stock_id)
    db.session.delete(stock)
    db.session.commit()
    
    return jsonify({'message': 'Stock deleted successfully'}), 200

# ============= PORTFOLIOS ENDPOINTS =============
@app.route('/api/portfolios', methods=['GET'])
def get_portfolios():
    """Get all portfolios"""
    portfolios = Portfolio.query.all()
    return jsonify({'portfolios': [portfolio.to_dict() for portfolio in portfolios]})

@app.route('/api/portfolios/<int:portfolio_id>', methods=['GET'])
def get_portfolio(portfolio_id):
    """Get a specific portfolio by ID"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    return jsonify(portfolio.to_dict())

@app.route('/api/portfolios', methods=['POST'])
def create_portfolio():
    """Create a new portfolio"""
    data = request.get_json()
    
    portfolio = Portfolio(
        name=data['name'],
        description=data.get('description'),
        cash_balance=data.get('cash_balance', 0.0)
    )
    
    db.session.add(portfolio)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio created successfully', 'portfolio': portfolio.to_dict()}), 201

@app.route('/api/portfolios/<int:portfolio_id>', methods=['PUT'])
def update_portfolio(portfolio_id):
    """Update a portfolio"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    data = request.get_json()
    
    portfolio.name = data.get('name', portfolio.name)
    portfolio.description = data.get('description', portfolio.description)
    portfolio.cash_balance = data.get('cash_balance', portfolio.cash_balance)
    portfolio.total_value = data.get('total_value', portfolio.total_value)
    
    db.session.commit()
    
    return jsonify({'message': 'Portfolio updated successfully', 'portfolio': portfolio.to_dict()})

@app.route('/api/portfolios/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    """Delete a portfolio"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    db.session.delete(portfolio)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio deleted successfully'}), 200

# ============= TRANSACTIONS ENDPOINTS =============
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions"""
    portfolio_id = request.args.get('portfolio_id', type=int)
    
    if portfolio_id:
        transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()
    else:
        transactions = Transaction.query.all()
    
    return jsonify({'transactions': [txn.to_dict() for txn in transactions]})

@app.route('/api/transactions/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Get a specific transaction by ID"""
    transaction = Transaction.query.get_or_404(transaction_id)
    return jsonify(transaction.to_dict())

@app.route('/api/transactions', methods=['POST'])
def create_transaction():
    """Create a new transaction"""
    data = request.get_json()
    
    # Verify portfolio and stock exist
    portfolio = Portfolio.query.get_or_404(data['portfolio_id'])
    stock = Stock.query.get_or_404(data['stock_id'])
    
    transaction = Transaction(
        portfolio_id=data['portfolio_id'],
        stock_id=data['stock_id'],
        transaction_type=data['transaction_type'].upper(),
        quantity=data['quantity'],
        price=data['price'],
        total_amount=data['quantity'] * data['price'],
        notes=data.get('notes')
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({'message': 'Transaction created successfully', 'transaction': transaction.to_dict()}), 201

@app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Delete a transaction"""
    transaction = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    
    return jsonify({'message': 'Transaction deleted successfully'}), 200

# ============= WATCHLIST ENDPOINTS =============
@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get all watchlist items"""
    watchlist = WatchList.query.all()
    return jsonify({'watchlist': [item.to_dict() for item in watchlist]})

@app.route('/api/watchlist/<int:watchlist_id>', methods=['GET'])
def get_watchlist_item(watchlist_id):
    """Get a specific watchlist item by ID"""
    item = WatchList.query.get_or_404(watchlist_id)
    return jsonify(item.to_dict())

@app.route('/api/watchlist', methods=['POST'])
def create_watchlist_item():
    """Add a stock to watchlist"""
    data = request.get_json()
    
    # Verify stock exists
    stock = Stock.query.get_or_404(data['stock_id'])
    
    # Check if stock is already in watchlist
    existing = WatchList.query.filter_by(stock_id=data['stock_id']).first()
    if existing:
        return jsonify({'error': 'Stock already in watchlist'}), 400
    
    watchlist_item = WatchList(
        stock_id=data['stock_id'],
        target_price=data.get('target_price'),
        notes=data.get('notes')
    )
    
    db.session.add(watchlist_item)
    db.session.commit()
    
    return jsonify({'message': 'Added to watchlist successfully', 'watchlist_item': watchlist_item.to_dict()}), 201

@app.route('/api/watchlist/<int:watchlist_id>', methods=['PUT'])
def update_watchlist_item(watchlist_id):
    """Update a watchlist item"""
    item = WatchList.query.get_or_404(watchlist_id)
    data = request.get_json()
    
    item.target_price = data.get('target_price', item.target_price)
    item.notes = data.get('notes', item.notes)
    
    db.session.commit()
    
    return jsonify({'message': 'Watchlist item updated successfully', 'watchlist_item': item.to_dict()})

@app.route('/api/watchlist/<int:watchlist_id>', methods=['DELETE'])
def delete_watchlist_item(watchlist_id):
    """Remove a stock from watchlist"""
    item = WatchList.query.get_or_404(watchlist_id)
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'message': 'Removed from watchlist successfully'}), 200

# ============= OHLCV DATA ENDPOINTS =============
@app.route('/api/ohlcv', methods=['GET'])
def get_ohlcv_data():
    """
    Get OHLCV data with filters
    Query parameters:
    - symbol: Stock symbol (e.g., RELIANCE.NS)
    - start_date: Start date (ISO format)
    - end_date: End date (ISO format)
    - limit: Number of records to return (default: 100)
    """
    symbol = request.args.get('symbol')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', type=int, default=100)
    
    query = OHLCV.query
    
    if symbol:
        query = query.filter_by(symbol=symbol)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(OHLCV.timestamp >= start_dt)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use ISO format.'}), 400
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(OHLCV.timestamp <= end_dt)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use ISO format.'}), 400
    
    # Order by timestamp descending (latest first)
    query = query.order_by(OHLCV.timestamp.desc())
    
    # Apply limit
    ohlcv_data = query.limit(limit).all()
    
    return jsonify({
        'count': len(ohlcv_data),
        'data': [item.to_dict() for item in ohlcv_data]
    })

@app.route('/api/ohlcv/latest', methods=['GET'])
def get_latest_ohlcv():
    """Get latest OHLCV data for all stocks or specific symbol"""
    symbol = request.args.get('symbol')
    
    if symbol:
        # Get latest data for specific symbol
        latest = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.desc()).first()
        if not latest:
            return jsonify({'error': f'No data found for {symbol}'}), 404
        return jsonify(latest.to_dict())
    else:
        # Get latest data for all symbols
        from sqlalchemy import func
        
        # Subquery to get max timestamp for each symbol
        subquery = db.session.query(
            OHLCV.symbol,
            func.max(OHLCV.timestamp).label('max_timestamp')
        ).group_by(OHLCV.symbol).subquery()
        
        # Join to get full records
        latest_data = db.session.query(OHLCV).join(
            subquery,
            (OHLCV.symbol == subquery.c.symbol) & (OHLCV.timestamp == subquery.c.max_timestamp)
        ).all()
        
        return jsonify({
            'count': len(latest_data),
            'data': [item.to_dict() for item in latest_data]
        })

@app.route('/api/ohlcv/symbols', methods=['GET'])
def get_available_symbols():
    """Get list of all symbols with OHLCV data"""
    symbols = db.session.query(OHLCV.symbol).distinct().all()
    return jsonify({
        'count': len(symbols),
        'symbols': [s[0] for s in symbols]
    })

@app.route('/api/ohlcv/fetch', methods=['POST'])
def trigger_fetch():
    """Manually trigger OHLCV data fetch"""
    try:
        fetch_ohlcv_data()
        return jsonify({'message': 'OHLCV data fetch triggered successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ohlcv/historical', methods=['POST'])
def fetch_historical():
    """
    Fetch historical OHLCV data for specific symbol
    Body: {"symbol": "RELIANCE.NS", "period": "1mo", "interval": "15m"}
    """
    data = request.get_json()
    symbol = data.get('symbol')
    period = data.get('period', '1mo')
    interval = data.get('interval', '15m')
    
    if not symbol:
        return jsonify({'error': 'Symbol is required'}), 400
    
    try:
        count = fetch_historical_ohlcv(symbol, period, interval)
        return jsonify({
            'message': f'Historical data fetch completed for {symbol}',
            'records_added': count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ohlcv/stats/<symbol>', methods=['GET'])
def get_ohlcv_stats(symbol):
    """Get statistics for a specific symbol"""
    # Get data for last 24 hours
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    data = OHLCV.query.filter(
        OHLCV.symbol == symbol,
        OHLCV.timestamp >= yesterday
    ).order_by(OHLCV.timestamp.asc()).all()
    
    if not data:
        return jsonify({'error': f'No recent data found for {symbol}'}), 404
    
    # Calculate statistics
    prices = [d.close for d in data]
    volumes = [d.volume for d in data]
    
    stats = {
        'symbol': symbol,
        'latest_price': data[-1].close,
        'latest_timestamp': data[-1].timestamp.isoformat(),
        'day_high': max([d.high for d in data]),
        'day_low': min([d.low for d in data]),
        'day_open': data[0].open,
        'day_close': data[-1].close,
        'price_change': data[-1].close - data[0].open,
        'price_change_percent': ((data[-1].close - data[0].open) / data[0].open * 100) if data[0].open != 0 else 0,
        'total_volume': sum(volumes),
        'average_price': sum(prices) / len(prices),
        'data_points': len(data)
    }
    
    return jsonify(stats)

@app.route('/api/ohlcv/initialize-all', methods=['POST'])
def trigger_initialize_all():
    """Trigger initialization of 5 years historical data for all stocks"""
    # Run in background thread
    thread = threading.Thread(target=initialize_all_historical_data)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Historical data initialization started',
        'info': 'Connect to WebSocket for progress updates'
    }), 202

def refresh_latest_data():
    """Refresh latest OHLCV data for all stocks and cleanup old records (>5 years)"""
    with app.app_context():
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
        
        for idx, symbol in enumerate(symbols, 1):
            try:
                # Fetch latest data (previous day)
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='2d', interval='15m')
                
                if not hist.empty:
                    # Add new records
                    records_added = 0
                    for timestamp, row in hist.iterrows():
                        existing = OHLCV.query.filter_by(
                            symbol=symbol,
                            timestamp=timestamp.to_pydatetime()
                        ).first()
                        
                        if not existing:
                            new_ohlcv = OHLCV(
                                symbol=symbol,
                                timestamp=timestamp.to_pydatetime(),
                                open=float(row['Open']),
                                high=float(row['High']),
                                low=float(row['Low']),
                                close=float(row['Close']),
                                volume=int(row['Volume'])
                            )
                            db.session.add(new_ohlcv)
                            records_added += 1
                    
                    # Cleanup old records (older than 5 years)
                    old_records = OHLCV.query.filter(
                        OHLCV.symbol == symbol,
                        OHLCV.timestamp < five_years_ago
                    ).all()
                    
                    for record in old_records:
                        db.session.delete(record)
                        cleanup_count += 1
                    
                    db.session.commit()
                    success_count += 1
                    
                    # Emit progress
                    progress = int((idx / total) * 100)
                    socketio.emit('refresh_progress', {
                        'current': idx,
                        'total': total,
                        'progress': progress,
                        'symbol': symbol,
                        'records_added': records_added,
                        'records_cleaned': len(old_records),
                        'status': 'processing'
                    })
                    
            except Exception as e:
                logger.error(f"Error refreshing data for {symbol}: {str(e)}")
                db.session.rollback()
                continue
        
        # Final progress update
        socketio.emit('refresh_progress', {
            'current': total,
            'total': total,
            'progress': 100,
            'status': 'completed',
            'message': f'Refresh completed! {success_count}/{total} stocks updated. {cleanup_count} old records removed.'
        })
        
        logger.info(f"Data refresh completed. {success_count}/{total} stocks updated. {cleanup_count} old records removed.")

@app.route('/api/ohlcv/refresh', methods=['POST'])
def trigger_refresh():
    """Trigger refresh of latest OHLCV data and cleanup old records"""
    # Run in background thread
    thread = threading.Thread(target=refresh_latest_data)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Data refresh started',
        'info': 'Connect to WebSocket for progress updates'
    }), 202

@app.route('/api/ohlcv/sector-heatmap', methods=['GET'])
def get_sector_heatmap():
    """Get sector-wise performance data for heatmap with date range filters"""
    try:
        from sqlalchemy import func
        
        # Get filter parameters
        duration = request.args.get('duration', '1d')  # 1d, 1w, 1m, 3m, 6m, 1y, ytd
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Calculate date range based on duration or custom dates
        end_datetime = datetime.now(timezone.utc)
        
        if start_date and end_date:
            # Use custom date range
            try:
                start_datetime = datetime.fromisoformat(start_date)
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}), 400
        else:
            # Use preset duration
            duration_map = {
                '1d': timedelta(days=1),
                '1w': timedelta(weeks=1),
                '1m': timedelta(days=30),
                '3m': timedelta(days=90),
                '6m': timedelta(days=180),
                '1y': timedelta(days=365),
                'ytd': None  # Year to date - special handling
            }
            
            if duration == 'ytd':
                # Year to date
                start_datetime = datetime(end_datetime.year, 1, 1)
            elif duration in duration_map:
                start_datetime = end_datetime - duration_map[duration]
            else:
                return jsonify({'error': 'Invalid duration. Use: 1d, 1w, 1m, 3m, 6m, 1y, ytd'}), 400
        
        # Get latest data point for each symbol (within end_datetime)
        latest_subquery = db.session.query(
            OHLCV.symbol,
            func.max(OHLCV.timestamp).label('max_timestamp')
        ).filter(
            OHLCV.timestamp <= end_datetime
        ).group_by(OHLCV.symbol).subquery()
        
        latest_data = db.session.query(OHLCV).join(
            latest_subquery,
            (OHLCV.symbol == latest_subquery.c.symbol) & 
            (OHLCV.timestamp == latest_subquery.c.max_timestamp)
        ).all()
        
        # Get earliest data point for each symbol (within date range)
        earliest_subquery = db.session.query(
            OHLCV.symbol,
            func.min(OHLCV.timestamp).label('min_timestamp')
        ).filter(
            OHLCV.timestamp >= start_datetime,
            OHLCV.timestamp <= end_datetime
        ).group_by(OHLCV.symbol).subquery()
        
        earliest_data = db.session.query(OHLCV).join(
            earliest_subquery,
            (OHLCV.symbol == earliest_subquery.c.symbol) & 
            (OHLCV.timestamp == earliest_subquery.c.min_timestamp)
        ).all()
        
        # Create mapping for latest prices
        latest_prices = {item.symbol: item for item in latest_data}
        earliest_prices = {item.symbol: item for item in earliest_data}
        
        # Calculate price changes
        stock_data = {}
        for symbol in latest_prices:
            if symbol in earliest_prices:
                latest = latest_prices[symbol]
                earliest = earliest_prices[symbol]
                
                price_change = ((latest.close - earliest.open) / earliest.open * 100) if earliest.open != 0 else 0
                
                # Calculate total volume for the period
                volume_query = db.session.query(func.sum(OHLCV.volume)).filter(
                    OHLCV.symbol == symbol,
                    OHLCV.timestamp >= start_datetime,
                    OHLCV.timestamp <= end_datetime
                ).scalar()
                
                stock_data[symbol] = {
                    'current_price': latest.close,
                    'start_price': earliest.open,
                    'price_change_percent': price_change,
                    'volume': volume_query or 0,
                    'high': latest.high,
                    'low': latest.low
                }
        
        # Group by sector
        all_stocks = get_all_stocks()
        sector_performance = {}
        
        for stock in all_stocks:
            sector = stock['sector']
            symbol = stock['symbol']
            
            if symbol in stock_data:
                if sector not in sector_performance:
                    sector_performance[sector] = {
                        'sector': sector,
                        'stocks': [],
                        'total_stocks': 0,
                        'avg_change': 0,
                        'total_volume': 0
                    }
                
                sector_performance[sector]['stocks'].append({
                    'symbol': symbol,
                    'name': stock['name'],
                    'price_change': stock_data[symbol]['price_change_percent'],
                    'current_price': stock_data[symbol]['current_price'],
                    'start_price': stock_data[symbol]['start_price'],
                    'volume': stock_data[symbol]['volume'],
                    'high': stock_data[symbol]['high'],
                    'low': stock_data[symbol]['low']
                })
        
        # Calculate sector averages and sort stocks by performance
        heatmap_data = []
        for sector, data in sector_performance.items():
            if data['stocks']:
                avg_change = sum(s['price_change'] for s in data['stocks']) / len(data['stocks'])
                total_volume = sum(s['volume'] for s in data['stocks'])
                
                # Sort stocks by price change (top performers)
                sorted_stocks = sorted(data['stocks'], key=lambda x: x['price_change'], reverse=True)
                
                heatmap_data.append({
                    'sector': sector,
                    'stock_count': len(data['stocks']),
                    'avg_price_change': round(avg_change, 2),
                    'total_volume': total_volume,
                    'stocks': sorted_stocks[:5]  # Top 5 performers
                })
        
        # Sort sectors by average price change
        heatmap_data.sort(key=lambda x: x['avg_price_change'], reverse=True)
        
        return jsonify({
            'heatmap_data': heatmap_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'filter': {
                'duration': duration,
                'start_date': start_datetime.isoformat(),
                'end_date': end_datetime.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating sector heatmap: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============= NIFTY 500 STOCK INFO ENDPOINTS =============
@app.route('/api/nifty500/stocks', methods=['GET'])
def get_nifty500_all_stocks():
    """Get all Nifty 500 stocks with complete information"""
    stocks = get_all_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@app.route('/api/nifty500/stock/<symbol>', methods=['GET'])
def get_nifty500_stock_info(symbol):
    """Get information for a specific stock"""
    stock = get_stock_by_symbol(symbol)
    if stock:
        return jsonify(stock)
    return jsonify({'error': f'Stock {symbol} not found'}), 404

@app.route('/api/nifty500/sectors', methods=['GET'])
def get_nifty500_sectors():
    """Get all unique sectors"""
    sectors = get_all_sectors()
    return jsonify({
        'count': len(sectors),
        'sectors': sectors
    })

@app.route('/api/nifty500/sector/<sector>', methods=['GET'])
def get_nifty500_stocks_by_sector(sector):
    """Get all stocks in a specific sector"""
    stocks = get_stocks_by_sector(sector)
    return jsonify({
        'sector': sector,
        'count': len(stocks),
        'stocks': stocks
    })

@app.route('/api/nifty500/nifty50', methods=['GET'])
def get_nifty50():
    """Get all Nifty 50 stocks"""
    stocks = get_nifty50_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@app.route('/api/nifty500/nifty200', methods=['GET'])
def get_nifty200():
    """Get all Nifty 200 stocks"""
    stocks = get_nifty200_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@app.route('/api/nifty500/search', methods=['GET'])
def search_nifty500_stocks():
    """Search stocks by name or symbol"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    results = search_stocks(query)
    return jsonify({
        'query': query,
        'count': len(results),
        'results': results
    })

@app.route('/api/nifty500/count', methods=['GET'])
def get_nifty500_count():
    """Get total count of stocks"""
    count = get_stock_count()
    return jsonify({'total_stocks': count})

# ============= DATABASE VIEWER ENDPOINTS =============
@app.route('/api/database/tables', methods=['GET'])
def get_database_tables():
    """Get list of all database tables"""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    table_info = {}
    for table in tables:
        # Get row count for each table
        result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
        count = result.scalar()
        table_info[table] = {'row_count': count}
    
    return jsonify({
        'tables': tables,
        'details': table_info
    })

@app.route('/api/database/view/<table_name>', methods=['GET'])
def view_table_data(table_name):
    """View data from any table"""
    try:
        limit = request.args.get('limit', type=int, default=100)
        offset = request.args.get('offset', type=int, default=0)
        
        # Get table data
        query = db.text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset")
        result = db.session.execute(query, {'limit': limit, 'offset': offset})
        
        # Get column names
        columns = result.keys()
        
        # Fetch rows
        rows = []
        for row in result:
            rows.append(dict(zip(columns, row)))
        
        # Get total count
        count_query = db.text(f"SELECT COUNT(*) FROM {table_name}")
        total_count = db.session.execute(count_query).scalar()
        
        return jsonify({
            'table': table_name,
            'columns': list(columns),
            'rows': rows,
            'total_count': total_count,
            'returned_count': len(rows),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/nifty500/initialize', methods=['POST'])
def initialize_stocks_from_nifty500():
    """Initialize stocks table with all Nifty 500 stocks data"""
    try:
        stocks_data = get_all_stocks()
        added_count = 0
        updated_count = 0
        
        for stock_data in stocks_data:
            symbol = get_symbol_without_suffix(stock_data['symbol'])
            
            # Check if stock already exists
            existing_stock = Stock.query.filter_by(symbol=symbol).first()
            
            if existing_stock:
                # Update existing stock
                existing_stock.name = stock_data['name']
                existing_stock.sector = stock_data['sector']
                updated_count += 1
            else:
                # Create new stock
                new_stock = Stock(
                    symbol=symbol,
                    name=stock_data['name'],
                    sector=stock_data['sector']
                )
                db.session.add(new_stock)
                added_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Stocks table initialized successfully',
            'added': added_count,
            'updated': updated_count,
            'total': added_count + updated_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ===== TECHNICAL ANALYSIS ENDPOINTS =====

@app.route('/api/analysis/stocks', methods=['GET'])
def get_analysis_data():
    """Get technical analysis data for all stocks with indicators based on 1 year of data"""
    try:
        import pandas_ta as ta
        
        # Use minimum 1 year of historical data for analysis
        end_datetime = datetime.now(timezone.utc)
        start_datetime = end_datetime - timedelta(days=365)  # 1 year of data
        
        # Get all stocks
        stocks = get_all_stocks()
        analysis_data = []
        
        for stock in stocks:
            symbol = stock['symbol']
            
            # Get OHLCV data for the symbol (1 year)
            ohlcv_records = OHLCV.query.filter(
                OHLCV.symbol == symbol,
                OHLCV.timestamp >= start_datetime,
                OHLCV.timestamp <= end_datetime
            ).order_by(OHLCV.timestamp.asc()).all()
            
            if len(ohlcv_records) < 30:  # Need minimum 30 data points for basic indicators
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume
            } for r in ohlcv_records])
            
            if df.empty:
                continue
            
            try:
                # Calculate indicators
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['ema_21'] = ta.ema(df['close'], length=21)
                df['ema_44'] = ta.ema(df['close'], length=44)
                df['ema_200'] = ta.ema(df['close'], length=200)
                
                # Calculate MACD
                macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
                if macd is not None and not macd.empty:
                    df['macd'] = macd[f'MACD_12_26_9']
                    df['macd_signal'] = macd[f'MACDs_12_26_9']
                    df['macd_hist'] = macd[f'MACDh_12_26_9']
                
                # Get latest values
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                
                # Determine MACD crossover
                macd_crossover = 'Neutral'
                if pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                    if pd.notna(prev['macd']) and pd.notna(prev['macd_signal']):
                        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
                            macd_crossover = 'Bullish'
                        elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
                            macd_crossover = 'Bearish'
                        elif latest['macd'] > latest['macd_signal']:
                            macd_crossover = 'Bullish'
                        elif latest['macd'] < latest['macd_signal']:
                            macd_crossover = 'Bearish'
                
                # Determine EMA crossovers (price crosses above EMA)
                ema_21_crossover = 'No'
                ema_44_crossover = 'No'
                ema_200_crossover = 'No'
                
                if pd.notna(latest['ema_21']) and pd.notna(prev['ema_21']):
                    if latest['close'] > latest['ema_21'] and prev['close'] <= prev['ema_21']:
                        ema_21_crossover = 'Yes'
                    elif latest['close'] > latest['ema_21']:
                        ema_21_crossover = 'Above'
                
                if pd.notna(latest['ema_44']) and pd.notna(prev['ema_44']):
                    if latest['close'] > latest['ema_44'] and prev['close'] <= prev['ema_44']:
                        ema_44_crossover = 'Yes'
                    elif latest['close'] > latest['ema_44']:
                        ema_44_crossover = 'Above'
                
                if pd.notna(latest['ema_200']) and pd.notna(prev['ema_200']):
                    if latest['close'] > latest['ema_200'] and prev['close'] <= prev['ema_200']:
                        ema_200_crossover = 'Yes'
                    elif latest['close'] > latest['ema_200']:
                        ema_200_crossover = 'Above'
                
                analysis_data.append({
                    'symbol': symbol,
                    'name': stock['name'],
                    'sector': stock.get('sector', 'N/A'),
                    'rsi': round(float(latest['rsi']), 2) if pd.notna(latest['rsi']) else None,
                    'macd_crossover': macd_crossover,
                    'ema_21_crossover': ema_21_crossover,
                    'ema_44_crossover': ema_44_crossover,
                    'ema_200_crossover': ema_200_crossover,
                    'current_price': float(latest['close'])
                })
                
            except Exception as e:
                logging.error(f"Error calculating indicators for {symbol}: {str(e)}")
                continue
        
        logging.info(f"Analysis completed: {len(analysis_data)} stocks processed out of {len(stocks)} total stocks")
        
        return jsonify({
            'analysis_data': analysis_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_stocks': len(analysis_data),
            'total_in_universe': len(stocks)
        })
        
    except Exception as e:
        logging.error(f"Error in get_analysis_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/chart/<symbol>', methods=['GET'])
def get_chart_data(symbol):
    """Get detailed chart data with indicators for a specific stock (all available data)"""
    try:
        import pandas_ta as ta
        
        # Get all OHLCV data for the symbol
        ohlcv_records = OHLCV.query.filter(
            OHLCV.symbol == symbol
        ).order_by(OHLCV.timestamp.asc()).all()
        
        if not ohlcv_records:
            return jsonify({'error': 'No data found for this symbol'}), 404
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume
        } for r in ohlcv_records])
        
        # Set timestamp as index for resampling
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resample to daily intervals (1D)
        # Open: first value of the day
        # High: max value of the day
        # Low: min value of the day
        # Close: last value of the day
        # Volume: sum of the day
        df_daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Reset index to get timestamp as column
        df_daily.reset_index(inplace=True)
        
        # Calculate indicators on daily data
        df_daily['rsi'] = ta.rsi(df_daily['close'], length=14)
        df_daily['ema_21'] = ta.ema(df_daily['close'], length=21)
        df_daily['ema_44'] = ta.ema(df_daily['close'], length=44)
        df_daily['ema_200'] = ta.ema(df_daily['close'], length=200)
        
        # Calculate MACD
        macd = ta.macd(df_daily['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df_daily['macd'] = macd[f'MACD_12_26_9']
            df_daily['macd_signal'] = macd[f'MACDs_12_26_9']
            df_daily['macd_hist'] = macd[f'MACDh_12_26_9']
        
        # Convert to JSON-serializable format
        chart_data = []
        for _, row in df_daily.iterrows():
            chart_data.append({
                'timestamp': row['timestamp'].isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'rsi': float(row['rsi']) if pd.notna(row['rsi']) else None,
                'ema_21': float(row['ema_21']) if pd.notna(row['ema_21']) else None,
                'ema_44': float(row['ema_44']) if pd.notna(row['ema_44']) else None,
                'ema_200': float(row['ema_200']) if pd.notna(row['ema_200']) else None,
                'macd': float(row['macd']) if pd.notna(row.get('macd')) else None,
                'macd_signal': float(row['macd_signal']) if pd.notna(row.get('macd_signal')) else None,
                'macd_hist': float(row['macd_hist']) if pd.notna(row.get('macd_hist')) else None
            })
        
        # Get stock info
        stock_info = get_stock_by_symbol(symbol)
        
        return jsonify({
            'symbol': symbol,
            'name': stock_info['name'] if stock_info else symbol,
            'sector': stock_info.get('sector', 'N/A') if stock_info else 'N/A',
            'chart_data': chart_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error in get_chart_data for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
