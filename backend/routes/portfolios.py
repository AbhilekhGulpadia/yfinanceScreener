from flask import Blueprint, jsonify, request
from extensions import db
from models import Portfolio

portfolios_bp = Blueprint('portfolios', __name__)

@portfolios_bp.route('/api/portfolios', methods=['GET'])
def get_portfolios():
    """Get all portfolios"""
    portfolios = Portfolio.query.all()
    return jsonify({'portfolios': [portfolio.to_dict() for portfolio in portfolios]})

@portfolios_bp.route('/api/portfolios/<int:portfolio_id>', methods=['GET'])
def get_portfolio(portfolio_id):
    """Get a specific portfolio by ID"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    return jsonify(portfolio.to_dict())

@portfolios_bp.route('/api/portfolios', methods=['POST'])
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

@portfolios_bp.route('/api/portfolios/<int:portfolio_id>', methods=['PUT'])
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

@portfolios_bp.route('/api/portfolios/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    """Delete a portfolio"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    db.session.delete(portfolio)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio deleted successfully'}), 200
