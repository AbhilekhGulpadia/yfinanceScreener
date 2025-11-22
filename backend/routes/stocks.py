from flask import Blueprint, jsonify, request
from extensions import db
from models import Stock

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get all stocks"""
    stocks = Stock.query.all()
    return jsonify({'stocks': [stock.to_dict() for stock in stocks]})

@stocks_bp.route('/api/stocks/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    """Get a specific stock by ID"""
    stock = Stock.query.get_or_404(stock_id)
    return jsonify(stock.to_dict())

@stocks_bp.route('/api/stocks', methods=['POST'])
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

@stocks_bp.route('/api/stocks/<int:stock_id>', methods=['PUT'])
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

@stocks_bp.route('/api/stocks/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    """Delete a stock"""
    stock = Stock.query.get_or_404(stock_id)
    db.session.delete(stock)
    db.session.commit()
    
    return jsonify({'message': 'Stock deleted successfully'}), 200
