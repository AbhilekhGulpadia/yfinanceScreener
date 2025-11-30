"""
Weinstein Screening API Routes

Provides endpoints for accessing Weinstein Stage Analysis screening results.
"""

from flask import Blueprint, jsonify, request
from services.weinstein_screening import (
    get_weinstein_scores_for_latest_week,
    run_weinstein_screening
)
import logging

logger = logging.getLogger(__name__)

weinstein_bp = Blueprint('weinstein', __name__)


@weinstein_bp.route('/api/weinstein-scores', methods=['GET'])
def get_weinstein_scores():
    """
    Get Weinstein screening scores for all stocks in the latest week.
    
    Query Parameters:
        liquidity_threshold (int): Minimum 20-week avg trading value (default: 1000000)
    
    Returns:
        JSON array of stocks with their Weinstein scores and details
    """
    try:
        # Get liquidity threshold from query params
        liquidity_threshold = request.args.get('liquidity_threshold', type=int, default=1000000)
        
        logger.info(f"Fetching Weinstein scores with liquidity threshold: ₹{liquidity_threshold:,}")
        
        # Get screening results
        results = get_weinstein_scores_for_latest_week(liquidity_threshold)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'liquidity_threshold': liquidity_threshold,
            'data': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_weinstein_scores: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@weinstein_bp.route('/api/weinstein-scores/<symbol>', methods=['GET'])
def get_weinstein_score_for_symbol(symbol):
    """
    Get detailed Weinstein analysis for a specific stock.
    
    Args:
        symbol: Stock symbol
    
    Query Parameters:
        liquidity_threshold (int): Minimum 20-week avg trading value (default: 1000000)
        weeks (int): Number of recent weeks to return (default: 52)
    
    Returns:
        JSON object with detailed weekly data and filter results
    """
    try:
        liquidity_threshold = request.args.get('liquidity_threshold', type=int, default=1000000)
        weeks = request.args.get('weeks', type=int, default=52)
        
        logger.info(f"Fetching Weinstein details for {symbol}")
        
        # Run screening to get full processed data
        shortlist, processed_df = run_weinstein_screening(liquidity_threshold)
        
        if processed_df.empty:
            return jsonify({
                'success': False,
                'error': 'No data available'
            }), 404
        
        # Filter for the requested symbol
        symbol_data = processed_df[processed_df['symbol'] == symbol].copy()
        
        if symbol_data.empty:
            return jsonify({
                'success': False,
                'error': f'No data found for symbol {symbol}'
            }), 404
        
        # Sort by timestamp descending and limit to requested weeks
        symbol_data = symbol_data.sort_values('timestamp', ascending=False).head(weeks)
        
        # Convert to list of dicts
        weekly_data = []
        for _, row in symbol_data.iterrows():
            weekly_data.append({
                'timestamp': row['timestamp'].isoformat(),
                'open': round(float(row['open']), 2),
                'high': round(float(row['high']), 2),
                'low': round(float(row['low']), 2),
                'close': round(float(row['close']), 2),
                'volume': int(row['volume']),
                'ma30': round(float(row['ma30']), 2) if pd.notna(row['ma30']) else None,
                'ma30_slope': round(float(row['ma30_slope']), 4) if pd.notna(row['ma30_slope']) else None,
                'high_52w': round(float(row['high_52w']), 2) if pd.notna(row['high_52w']) else None,
                'avg_vol_10': int(row['avg_vol_10']) if pd.notna(row['avg_vol_10']) else None,
                'trading_value': round(float(row['trading_value']), 2) if pd.notna(row['trading_value']) else None,
                'avg_trading_value_20': round(float(row['avg_trading_value_20']), 2) if pd.notna(row['avg_trading_value_20']) else None,
                'rs': round(float(row['rs']), 4) if pd.notna(row['rs']) else None,
                'rs_slope': round(float(row['rs_slope']), 6) if pd.notna(row['rs_slope']) else None,
                'rs_52w_high': round(float(row['rs_52w_high']), 4) if pd.notna(row['rs_52w_high']) else None,
                'conditions': {
                    'liquidity': bool(row['cond_liquidity']),
                    'stage2': bool(row['cond_stage2']),
                    'breakout': bool(row['cond_breakout']),
                    'volume_confirm': bool(row['cond_volume_confirm']),
                    'rs_uptrend': bool(row['cond_rs_uptrend']),
                    'strong_rs': bool(row['cond_strong_rs']),
                    'low_resistance': bool(row['cond_low_resistance']),
                    'not_overextended': bool(row['cond_not_overextended']),
                    'all_passed': bool(row['cond_all_passed'])
                }
            })
        
        # Count how many weeks passed all filters
        weeks_passed = symbol_data['cond_all_passed'].sum()
        
        # Get stock info
        stock_info = {
            'symbol': symbol,
            'name': symbol_data.iloc[0]['name'],
            'sector': symbol_data.iloc[0]['sector']
        }
        
        return jsonify({
            'success': True,
            'stock': stock_info,
            'weeks_passed_filters': int(weeks_passed),
            'total_weeks': len(weekly_data),
            'weekly_data': weekly_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_weinstein_score_for_symbol for {symbol}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@weinstein_bp.route('/api/weinstein-shortlist', methods=['GET'])
def get_weinstein_shortlist():
    """
    Get shortlist of stocks that passed all Weinstein filters in the latest week.
    
    Query Parameters:
        liquidity_threshold (int): Minimum 20-week avg trading value (default: 1000000)
    
    Returns:
        JSON array of symbols that passed all filters
    """
    try:
        liquidity_threshold = request.args.get('liquidity_threshold', type=int, default=1000000)
        
        logger.info(f"Generating Weinstein shortlist with liquidity threshold: ₹{liquidity_threshold:,}")
        
        # Run screening
        shortlist, _ = run_weinstein_screening(liquidity_threshold)
        
        return jsonify({
            'success': True,
            'count': len(shortlist),
            'liquidity_threshold': liquidity_threshold,
            'shortlist': shortlist
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_weinstein_shortlist: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Import pandas for notna checks
import pandas as pd
