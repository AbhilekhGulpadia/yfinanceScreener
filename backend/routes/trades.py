"""
Trades API Routes

Endpoints for recording trades and calculating P/L with brokerage charges.
"""

from flask import Blueprint, jsonify, request
from extensions import db
from models import Trade, OHLCV
from services.brokerage_calculator import calculate_trade_charges, calculate_total_cost
from datetime import datetime, timezone
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

trades_bp = Blueprint('trades', __name__)


@trades_bp.route('/api/trades', methods=['POST'])
def record_trade():
    """
    Record a new trade with automatic charge calculations
    
    Body:
        symbol: Stock symbol
        trade_type: 'BUY' or 'SELL'
        quantity: Number of shares
        price: Price per share
        trade_date: Trade date/time (ISO format, optional, defaults to now)
        notes: Optional notes
    
    Returns:
        Created trade with calculated charges
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['symbol', 'trade_type', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate trade_type
        if data['trade_type'].upper() not in ['BUY', 'SELL']:
            return jsonify({
                'success': False,
                'error': 'trade_type must be BUY or SELL'
            }), 400
        
        # Calculate charges
        charges = calculate_trade_charges(
            data['trade_type'],
            data['quantity'],
            data['price']
        )
        
        # Parse trade date
        trade_date = None
        if 'trade_date' in data and data['trade_date']:
            try:
                trade_date = datetime.fromisoformat(data['trade_date'].replace('Z', '+00:00'))
            except:
                trade_date = datetime.now(timezone.utc)
        else:
            trade_date = datetime.now(timezone.utc)
        
        # Create trade record
        trade = Trade(
            symbol=data['symbol'],
            trade_type=data['trade_type'].upper(),
            quantity=data['quantity'],
            price=data['price'],
            trade_date=trade_date,
            brokerage=charges['brokerage'],
            stt=charges['stt'],
            exchange_charges=charges['exchange_charges'],
            gst=charges['gst'],
            sebi_charges=charges['sebi_charges'],
            stamp_duty=charges['stamp_duty'],
            total_charges=charges['total_charges'],
            notes=data.get('notes', '')
        )
        
        db.session.add(trade)
        db.session.commit()
        
        logger.info(f"Recorded {data['trade_type']} trade for {data['symbol']}: {data['quantity']} @ ₹{data['price']}")
        
        return jsonify({
            'success': True,
            'message': 'Trade recorded successfully',
            'data': trade.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error recording trade: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trades_bp.route('/api/trades', methods=['GET'])
def get_trades():
    """
    Get all trades with optional filters
    
    Query params:
        symbol: Filter by symbol (optional)
        start_date: Start date (ISO format, optional)
        end_date: End date (ISO format, optional)
    
    Returns:
        Array of trades
    """
    try:
        query = Trade.query
        
        # Filter by symbol
        symbol = request.args.get('symbol')
        if symbol:
            query = query.filter_by(symbol=symbol)
        
        # Filter by date range
        start_date = request.args.get('start_date')
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(Trade.trade_date >= start_dt)
            except:
                pass
        
        end_date = request.args.get('end_date')
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(Trade.trade_date <= end_dt)
            except:
                pass
        
        # Order by trade date descending
        trades = query.order_by(Trade.trade_date.desc()).all()
        
        return jsonify({
            'success': True,
            'count': len(trades),
            'data': [trade.to_dict() for trade in trades]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trades_bp.route('/api/trades/<int:id>', methods=['DELETE'])
def delete_trade(id):
    """
    Delete a trade
    
    Args:
        id: Trade ID
    
    Returns:
        Success message
    """
    try:
        trade = Trade.query.get(id)
        
        if not trade:
            return jsonify({
                'success': False,
                'error': 'Trade not found'
            }), 404
        
        db.session.delete(trade)
        db.session.commit()
        
        logger.info(f"Deleted trade {id}")
        
        return jsonify({
            'success': True,
            'message': 'Trade deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting trade: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trades_bp.route('/api/trades/portfolio', methods=['GET'])
def get_portfolio():
    """
    Get current portfolio positions from all trades
    
    Returns:
        Array of positions with holdings and P/L
    """
    try:
        # Get all trades grouped by symbol
        trades = Trade.query.order_by(Trade.symbol, Trade.trade_date).all()
        
        # Calculate positions
        positions = {}
        
        for trade in trades:
            symbol = trade.symbol
            
            if symbol not in positions:
                positions[symbol] = {
                    'symbol': symbol,
                    'quantity': 0,
                    'total_buy_value': 0,
                    'total_sell_value': 0,
                    'total_charges': 0,
                    'trades': []
                }
            
            pos = positions[symbol]
            
            if trade.trade_type == 'BUY':
                pos['quantity'] += trade.quantity
                pos['total_buy_value'] += (trade.quantity * trade.price)
            else:  # SELL
                pos['quantity'] -= trade.quantity
                pos['total_sell_value'] += (trade.quantity * trade.price)
            
            pos['total_charges'] += trade.total_charges
            pos['trades'].append(trade.to_dict())
        
        # Get current prices and calculate P/L
        result = []
        for symbol, pos in positions.items():
            if pos['quantity'] > 0:  # Only include open positions
                # Get current price
                latest_ohlcv = OHLCV.query.filter_by(
                    symbol=symbol
                ).order_by(OHLCV.timestamp.desc()).first()
                
                current_price = latest_ohlcv.close if latest_ohlcv else 0
                
                # Calculate average buy price
                avg_buy_price = pos['total_buy_value'] / pos['quantity'] if pos['quantity'] > 0 else 0
                
                # Calculate current value
                current_value = pos['quantity'] * current_price
                
                # Calculate unrealized P/L
                unrealized_pnl = current_value - pos['total_buy_value']
                unrealized_pnl_pct = (unrealized_pnl / pos['total_buy_value'] * 100) if pos['total_buy_value'] > 0 else 0
                
                result.append({
                    'symbol': symbol,
                    'quantity': pos['quantity'],
                    'avg_buy_price': round(avg_buy_price, 2),
                    'current_price': round(current_price, 2),
                    'investment': round(pos['total_buy_value'], 2),
                    'current_value': round(current_value, 2),
                    'unrealized_pnl': round(unrealized_pnl, 2),
                    'unrealized_pnl_pct': round(unrealized_pnl_pct, 2),
                    'total_charges': round(pos['total_charges'], 2)
                })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting portfolio: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trades_bp.route('/api/trades/pnl', methods=['GET'])
def get_pnl_analysis():
    """
    Get comprehensive P/L analysis
    
    Returns:
        Realized P/L, unrealized P/L, and total charges breakdown
    """
    try:
        # Get all trades
        trades = Trade.query.all()
        
        # Calculate positions and realized P/L
        positions = {}
        total_charges_breakdown = {
            'brokerage': 0,
            'stt': 0,
            'exchange_charges': 0,
            'gst': 0,
            'sebi_charges': 0,
            'stamp_duty': 0,
            'total': 0
        }
        
        for trade in trades:
            symbol = trade.symbol
            
            if symbol not in positions:
                positions[symbol] = {
                    'quantity': 0,
                    'buy_value': 0,
                    'sell_value': 0,
                    'realized_pnl': 0
                }
            
            pos = positions[symbol]
            
            if trade.trade_type == 'BUY':
                pos['quantity'] += trade.quantity
                pos['buy_value'] += (trade.quantity * trade.price)
            else:  # SELL
                # Calculate realized P/L for sold quantity
                if pos['quantity'] > 0:
                    avg_cost = pos['buy_value'] / pos['quantity']
                    realized = (trade.price - avg_cost) * trade.quantity
                    pos['realized_pnl'] += realized
                
                pos['quantity'] -= trade.quantity
                pos['sell_value'] += (trade.quantity * trade.price)
            
            # Accumulate charges
            total_charges_breakdown['brokerage'] += trade.brokerage
            total_charges_breakdown['stt'] += trade.stt
            total_charges_breakdown['exchange_charges'] += trade.exchange_charges
            total_charges_breakdown['gst'] += trade.gst
            total_charges_breakdown['sebi_charges'] += trade.sebi_charges
            total_charges_breakdown['stamp_duty'] += trade.stamp_duty
            total_charges_breakdown['total'] += trade.total_charges
        
        # Calculate totals
        total_realized_pnl = sum(pos['realized_pnl'] for pos in positions.values())
        total_unrealized_pnl = 0
        total_investment = 0
        total_current_value = 0
        
        # Calculate unrealized P/L for open positions
        for symbol, pos in positions.items():
            if pos['quantity'] > 0:
                latest_ohlcv = OHLCV.query.filter_by(
                    symbol=symbol
                ).order_by(OHLCV.timestamp.desc()).first()
                
                current_price = latest_ohlcv.close if latest_ohlcv else 0
                current_value = pos['quantity'] * current_price
                unrealized = current_value - pos['buy_value']
                
                total_unrealized_pnl += unrealized
                total_investment += pos['buy_value']
                total_current_value += current_value
        
        # Round all values
        for key in total_charges_breakdown:
            total_charges_breakdown[key] = round(total_charges_breakdown[key], 2)
        
        return jsonify({
            'success': True,
            'data': {
                'realized_pnl': round(total_realized_pnl, 2),
                'unrealized_pnl': round(total_unrealized_pnl, 2),
                'total_pnl': round(total_realized_pnl + total_unrealized_pnl, 2),
                'total_investment': round(total_investment, 2),
                'total_current_value': round(total_current_value, 2),
                'charges_breakdown': total_charges_breakdown,
                'net_pnl': round(total_realized_pnl + total_unrealized_pnl - total_charges_breakdown['total'], 2)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting P/L analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
