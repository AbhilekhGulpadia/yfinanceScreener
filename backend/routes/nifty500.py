from flask import Blueprint, jsonify, request
from extensions import db
from models import Stock
from nifty500 import (
    get_all_stocks, get_stock_by_symbol, get_all_sectors,
    get_stocks_by_sector, get_nifty50_stocks, get_nifty200_stocks,
    search_stocks, get_stock_count, get_symbol_without_suffix
)

nifty500_bp = Blueprint('nifty500', __name__)

@nifty500_bp.route('/api/nifty500/stocks', methods=['GET'])
def get_nifty500_all_stocks():
    """Get all Nifty 500 stocks with complete information"""
    stocks = get_all_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@nifty500_bp.route('/api/nifty500/stock/<symbol>', methods=['GET'])
def get_nifty500_stock_info(symbol):
    """Get information for a specific stock"""
    stock = get_stock_by_symbol(symbol)
    if stock:
        return jsonify(stock)
    return jsonify({'error': f'Stock {symbol} not found'}), 404

@nifty500_bp.route('/api/nifty500/sectors', methods=['GET'])
def get_nifty500_sectors():
    """Get all unique sectors"""
    sectors = get_all_sectors()
    return jsonify({
        'count': len(sectors),
        'sectors': sectors
    })

@nifty500_bp.route('/api/nifty500/sector/<sector>', methods=['GET'])
def get_nifty500_stocks_by_sector(sector):
    """Get all stocks in a specific sector"""
    stocks = get_stocks_by_sector(sector)
    return jsonify({
        'sector': sector,
        'count': len(stocks),
        'stocks': stocks
    })

@nifty500_bp.route('/api/nifty500/nifty50', methods=['GET'])
def get_nifty50():
    """Get all Nifty 50 stocks"""
    stocks = get_nifty50_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@nifty500_bp.route('/api/nifty500/nifty200', methods=['GET'])
def get_nifty200():
    """Get all Nifty 200 stocks"""
    stocks = get_nifty200_stocks()
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })

@nifty500_bp.route('/api/nifty500/search', methods=['GET'])
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

@nifty500_bp.route('/api/nifty500/count', methods=['GET'])
def get_nifty500_count():
    """Get total count of stocks"""
    count = get_stock_count()
    return jsonify({'total_stocks': count})

@nifty500_bp.route('/api/nifty500/initialize', methods=['POST'])
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
