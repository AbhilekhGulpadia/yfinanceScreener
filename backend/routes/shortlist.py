"""
Shortlist API Routes

Endpoints for managing shortlisted stocks from Weinstein screening.
"""

from flask import Blueprint, jsonify, request
from extensions import db
from models import ShortlistedStock, OHLCV
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

shortlist_bp = Blueprint('shortlist', __name__)


@shortlist_bp.route('/api/shortlist', methods=['POST'])
def add_to_shortlist():
    """
    Add a stock to the shortlist
    
    Body:
        symbol: Stock symbol
        name: Stock name
        sector: Sector
        price: Current price
        score: Weinstein score
        stage: Weinstein stage
        ma30: 30-week MA
        rs: Relative strength
        notes: Optional notes
    
    Returns:
        Created shortlist entry
    """
    try:
        data = request.get_json()
        
        # Check if stock is already shortlisted
        existing = ShortlistedStock.query.filter_by(symbol=data['symbol']).first()
        if existing:
            return jsonify({
                'success': False,
                'error': f"{data['symbol']} is already in your shortlist"
            }), 400
        
        # Create new shortlist entry
        shortlisted_stock = ShortlistedStock(
            symbol=data['symbol'],
            name=data.get('name'),
            sector=data.get('sector'),
            price_at_shortlist=data.get('price'),
            score=data.get('score'),
            stage=data.get('stage'),
            ma30=data.get('ma30'),
            rs=data.get('rs'),
            notes=data.get('notes', '')
        )
        
        db.session.add(shortlisted_stock)
        db.session.commit()
        
        logger.info(f"Added {data['symbol']} to shortlist")
        
        return jsonify({
            'success': True,
            'message': f"{data['symbol']} added to shortlist",
            'data': shortlisted_stock.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding to shortlist: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@shortlist_bp.route('/api/shortlist', methods=['GET'])
def get_shortlist():
    """
    Get all shortlisted stocks with current prices
    
    Returns:
        Array of shortlisted stocks with current prices
    """
    try:
        shortlisted_stocks = ShortlistedStock.query.order_by(
            ShortlistedStock.shortlisted_at.desc()
        ).all()
        
        results = []
        for stock in shortlisted_stocks:
            stock_dict = stock.to_dict()
            
            # Get current price from latest OHLCV data
            latest_ohlcv = OHLCV.query.filter_by(
                symbol=stock.symbol
            ).order_by(OHLCV.timestamp.desc()).first()
            
            if latest_ohlcv:
                current_price = latest_ohlcv.close
                stock_dict['current_price'] = current_price
                
                # Calculate change percentage
                if stock.price_at_shortlist and stock.price_at_shortlist > 0:
                    change_pct = ((current_price - stock.price_at_shortlist) / stock.price_at_shortlist) * 100
                    stock_dict['change_percent'] = round(change_pct, 2)
                else:
                    stock_dict['change_percent'] = 0
            else:
                stock_dict['current_price'] = stock.price_at_shortlist
                stock_dict['change_percent'] = 0
            
            results.append(stock_dict)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'data': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting shortlist: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@shortlist_bp.route('/api/shortlist/<int:id>', methods=['DELETE'])
def remove_from_shortlist(id):
    """
    Remove a stock from the shortlist
    
    Args:
        id: Shortlist entry ID
    
    Returns:
        Success message
    """
    try:
        shortlisted_stock = ShortlistedStock.query.get(id)
        
        if not shortlisted_stock:
            return jsonify({
                'success': False,
                'error': 'Stock not found in shortlist'
            }), 404
        
        symbol = shortlisted_stock.symbol
        db.session.delete(shortlisted_stock)
        db.session.commit()
        
        logger.info(f"Removed {symbol} from shortlist")
        
        return jsonify({
            'success': True,
            'message': f"{symbol} removed from shortlist"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing from shortlist: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@shortlist_bp.route('/api/shortlist/<int:id>', methods=['PUT'])
def update_shortlist_notes(id):
    """
    Update notes for a shortlisted stock
    
    Args:
        id: Shortlist entry ID
    
    Body:
        notes: Updated notes
    
    Returns:
        Updated shortlist entry
    """
    try:
        shortlisted_stock = ShortlistedStock.query.get(id)
        
        if not shortlisted_stock:
            return jsonify({
                'success': False,
                'error': 'Stock not found in shortlist'
            }), 404
        
        data = request.get_json()
        shortlisted_stock.notes = data.get('notes', '')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Notes updated',
            'data': shortlisted_stock.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating shortlist notes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
