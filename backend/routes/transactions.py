from flask import Blueprint, jsonify, request
from extensions import db
from models import Transaction, Portfolio, Stock

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions"""
    portfolio_id = request.args.get('portfolio_id', type=int)
    
    if portfolio_id:
        transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()
    else:
        transactions = Transaction.query.all()
    
    return jsonify({'transactions': [txn.to_dict() for txn in transactions]})

@transactions_bp.route('/api/transactions/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Get a specific transaction by ID"""
    transaction = Transaction.query.get_or_404(transaction_id)
    return jsonify(transaction.to_dict())

@transactions_bp.route('/api/transactions', methods=['POST'])
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

@transactions_bp.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Delete a transaction"""
    transaction = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    
    return jsonify({'message': 'Transaction deleted successfully'}), 200
