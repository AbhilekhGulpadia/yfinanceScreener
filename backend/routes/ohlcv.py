from flask import Blueprint, jsonify, request, current_app
from extensions import db
from models import OHLCV
from services.data_fetcher import (
    fetch_ohlcv_data, fetch_historical_ohlcv, 
    initialize_all_historical_data, refresh_latest_data
)
from nifty500 import get_all_stocks
from datetime import datetime, timedelta, timezone
import threading
import gc
import logging

# Set up logging
logger = logging.getLogger(__name__)

ohlcv_bp = Blueprint('ohlcv', __name__)

@ohlcv_bp.route('/api/ohlcv', methods=['GET'])
def get_ohlcv_data_route():
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

@ohlcv_bp.route('/api/ohlcv/latest', methods=['GET'])
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

@ohlcv_bp.route('/api/ohlcv/symbols', methods=['GET'])
def get_available_symbols():
    """Get list of all symbols with OHLCV data"""
    symbols = db.session.query(OHLCV.symbol).distinct().all()
    return jsonify({
        'count': len(symbols),
        'symbols': [s[0] for s in symbols]
    })

@ohlcv_bp.route('/api/ohlcv/fetch', methods=['POST'])
def trigger_fetch():
    """Manually trigger OHLCV data fetch"""
    try:
        fetch_ohlcv_data()
        return jsonify({'message': 'OHLCV data fetch triggered successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ohlcv_bp.route('/api/ohlcv/historical', methods=['POST'])
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

@ohlcv_bp.route('/api/ohlcv/stats/<symbol>', methods=['GET'])
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

def run_with_context(app, func, *args, **kwargs):
    with app.app_context():
        func(*args, **kwargs)

@ohlcv_bp.route('/api/ohlcv/initialize-all', methods=['POST'])
def trigger_initialize_all():
    """Trigger initialization of 5 years historical data for all stocks"""
    # Run in background thread with app context
    app = current_app._get_current_object()
    thread = threading.Thread(target=run_with_context, args=(app, initialize_all_historical_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Historical data initialization started',
        'info': 'Connect to WebSocket for progress updates'
    }), 202

@ohlcv_bp.route('/api/ohlcv/refresh', methods=['POST'])
def trigger_refresh():
    """Trigger refresh of latest OHLCV data and cleanup old records"""
    # Run in background thread with app context
    app = current_app._get_current_object()
    thread = threading.Thread(target=run_with_context, args=(app, refresh_latest_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Data refresh started',
        'info': 'Connect to WebSocket for progress updates'
    }), 202

@ohlcv_bp.route('/api/ohlcv/sector-heatmap', methods=['GET'])
def get_sector_heatmap():
    """
    Get sector-wise performance data for heatmap with date range filters.
    Optimized to avoid N+1 queries.
    """
    try:
        from sqlalchemy import func
        
        # Get filter parameters
        duration = request.args.get('duration', '1d')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Calculate date range
        end_datetime = datetime.now(timezone.utc)
        
        if start_date and end_date:
            try:
                start_datetime = datetime.fromisoformat(start_date)
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}), 400
        else:
            duration_map = {
                '1d': timedelta(days=1),
                '1w': timedelta(weeks=1),
                '1m': timedelta(days=30),
                '3m': timedelta(days=90),
                '6m': timedelta(days=180),
                '1y': timedelta(days=365),
                'ytd': None
            }
            
            if duration == 'ytd':
                start_datetime = datetime(end_datetime.year, 1, 1, tzinfo=timezone.utc)
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
        
        # OPTIMIZED: Get all volume sums in a single query instead of N+1
        volume_subquery = db.session.query(
            OHLCV.symbol,
            func.sum(OHLCV.volume).label('total_volume')
        ).filter(
            OHLCV.timestamp >= start_datetime,
            OHLCV.timestamp <= end_datetime
        ).group_by(OHLCV.symbol).all()
        
        # Create mappings
        latest_prices = {item.symbol: item for item in latest_data}
        earliest_prices = {item.symbol: item for item in earliest_data}
        volume_map = {symbol: total_vol for symbol, total_vol in volume_subquery}
        
        # Clean up
        del latest_data
        del earliest_data
        del volume_subquery
        
        # Calculate price changes
        stock_data = {}
        for symbol in latest_prices:
            if symbol in earliest_prices:
                latest = latest_prices[symbol]
                earliest = earliest_prices[symbol]
                
                if earliest.open != 0:
                    price_change = ((latest.close - earliest.open) / earliest.open * 100)
                else:
                    price_change = 0
                
                stock_data[symbol] = {
                    'current_price': latest.close,
                    'start_price': earliest.open,
                    'price_change_percent': price_change,
                    'volume': volume_map.get(symbol, 0),
                    'high': latest.high,
                    'low': latest.low
                }
        
        del latest_prices
        del earliest_prices
        
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
        
        del stock_data
        
        # Process sectors
        temp_sector_data = []
        for sector, data in sector_performance.items():
            if data['stocks']:
                avg_change = sum(s['price_change'] for s in data['stocks']) / len(data['stocks'])
                total_volume = sum(s['volume'] for s in data['stocks'])
                
                sorted_stocks = sorted(data['stocks'], key=lambda x: abs(x['price_change']), reverse=True)
                
                temp_sector_data.append({
                    'sector': sector,
                    'stock_count': len(data['stocks']),
                    'avg_price_change': avg_change,
                    'total_volume': total_volume,
                    'stocks': sorted_stocks[:30]
                })
        
        del sector_performance
        
        # Sort and consolidate
        temp_sector_data.sort(key=lambda x: x['total_volume'], reverse=True)
        
        final_heatmap_data = []
        others_sector = {
            'sector': 'Others',
            'stock_count': 0,
            'avg_price_change': 0,
            'total_volume': 0,
            'stocks': []
        }
        
        MAX_SECTORS = 15
        
        for i, sector_data in enumerate(temp_sector_data):
            if i < MAX_SECTORS:
                sector_data['stocks'] = sector_data['stocks'][:30]
                sector_data['avg_price_change'] = round(sector_data['avg_price_change'], 2)
                final_heatmap_data.append(sector_data)
            else:
                others_sector['stock_count'] += sector_data['stock_count']
                others_sector['total_volume'] += sector_data['total_volume']
                others_sector['stocks'].extend(sector_data['stocks'])
        
        if others_sector['stock_count'] > 0:
            all_others_changes = [s['price_change'] for s in others_sector['stocks']]
            if all_others_changes:
                others_sector['avg_price_change'] = round(sum(all_others_changes) / len(all_others_changes), 2)
            
            others_sector['stocks'].sort(key=lambda x: abs(x['price_change']), reverse=True)
            others_sector['stocks'] = others_sector['stocks'][:30]
            
            final_heatmap_data.append(others_sector)
        
        final_heatmap_data.sort(key=lambda x: x['avg_price_change'], reverse=True)
        
        gc.collect()
        
        return jsonify({
            'heatmap_data': final_heatmap_data,
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
