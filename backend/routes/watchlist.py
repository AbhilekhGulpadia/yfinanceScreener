from flask import Blueprint, jsonify, request
from extensions import db
from models import WatchList, Stock

watchlist_bp = Blueprint('watchlist', __name__)

@watchlist_bp.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get all watchlist items"""
    watchlist = WatchList.query.all()
    return jsonify({'watchlist': [item.to_dict() for item in watchlist]})

@watchlist_bp.route('/api/watchlist/<int:watchlist_id>', methods=['GET'])
def get_watchlist_item(watchlist_id):
    """Get a specific watchlist item by ID"""
    item = WatchList.query.get_or_404(watchlist_id)
    return jsonify(item.to_dict())

@watchlist_bp.route('/api/watchlist', methods=['POST'])
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

@watchlist_bp.route('/api/watchlist/<int:watchlist_id>', methods=['PUT'])
def update_watchlist_item(watchlist_id):
    """Update a watchlist item"""
    item = WatchList.query.get_or_404(watchlist_id)
    data = request.get_json()
    
    item.target_price = data.get('target_price', item.target_price)
    item.notes = data.get('notes', item.notes)
    
    db.session.commit()
    
    return jsonify({'message': 'Watchlist item updated successfully', 'watchlist_item': item.to_dict()})

@watchlist_bp.route('/api/watchlist/<int:watchlist_id>', methods=['DELETE'])
def delete_watchlist_item(watchlist_id):
    """Remove a stock from watchlist"""
    item = WatchList.query.get_or_404(watchlist_id)
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'message': 'Removed from watchlist successfully'}), 200
