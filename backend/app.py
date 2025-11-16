from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from config import Config
from models import db, Stock, Portfolio, Transaction, WatchList, OHLCV
import yfinance as yf
from datetime import datetime, timedelta
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
                    existing.last_updated = datetime.utcnow()
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
    yesterday = datetime.utcnow() - timedelta(days=1)
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

@app.route('/api/ohlcv/sector-heatmap', methods=['GET'])
def get_sector_heatmap():
    """Get sector-wise performance data for heatmap"""
    try:
        # Get all stocks with their latest prices
        from sqlalchemy import func
        
        # Subquery to get max timestamp for each symbol
        subquery = db.session.query(
            OHLCV.symbol,
            func.max(OHLCV.timestamp).label('max_timestamp')
        ).group_by(OHLCV.symbol).subquery()
        
        # Join to get full records with latest prices
        latest_data = db.session.query(OHLCV).join(
            subquery,
            (OHLCV.symbol == subquery.c.symbol) & (OHLCV.timestamp == subquery.c.max_timestamp)
        ).all()
        
        # Get data from 24 hours ago for comparison
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Create mapping of symbol to latest price and previous price
        stock_data = {}
        for item in latest_data:
            # Get price from 24 hours ago
            prev_data = OHLCV.query.filter(
                OHLCV.symbol == item.symbol,
                OHLCV.timestamp >= yesterday,
                OHLCV.timestamp < item.timestamp
            ).order_by(OHLCV.timestamp.asc()).first()
            
            prev_price = prev_data.close if prev_data else item.close
            price_change = ((item.close - prev_price) / prev_price * 100) if prev_price != 0 else 0
            
            stock_data[item.symbol] = {
                'current_price': item.close,
                'previous_price': prev_price,
                'price_change_percent': price_change,
                'volume': item.volume
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
                    'volume': stock_data[symbol]['volume']
                })
        
        # Calculate sector averages
        heatmap_data = []
        for sector, data in sector_performance.items():
            if data['stocks']:
                avg_change = sum(s['price_change'] for s in data['stocks']) / len(data['stocks'])
                total_volume = sum(s['volume'] for s in data['stocks'])
                
                heatmap_data.append({
                    'sector': sector,
                    'stock_count': len(data['stocks']),
                    'avg_price_change': round(avg_change, 2),
                    'total_volume': total_volume,
                    'stocks': data['stocks'][:5]  # Top 5 stocks for tooltip
                })
        
        # Sort by average price change
        heatmap_data.sort(key=lambda x: x['avg_price_change'], reverse=True)
        
        return jsonify({
            'heatmap_data': heatmap_data,
            'timestamp': datetime.utcnow().isoformat()
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

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
