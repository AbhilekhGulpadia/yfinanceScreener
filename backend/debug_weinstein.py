"""
Debug script to test Weinstein screening logic and identify filter bottlenecks
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import Config
from extensions import db
from models import OHLCV
from services.weinstein_screening import (
    resample_to_weekly,
    resample_index_to_weekly,
    compute_indicators,
    apply_filters,
    get_or_create_index_data
)
from nifty500 import get_all_stocks
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app context
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def debug_weinstein_screening():
    """Debug the Weinstein screening to see where stocks are failing"""
    
    with app.app_context():
        logger.info("Starting Weinstein screening debug...")
        
        # Get index data
        index_daily = get_or_create_index_data()
        if index_daily.empty:
            logger.error("No index data available")
            return
        
        index_daily['timestamp'] = pd.to_datetime(index_daily['timestamp'])
        index_weekly = resample_index_to_weekly(index_daily)
        logger.info(f"Index weekly data: {len(index_weekly)} weeks")
        
        # Get all stocks
        all_stocks = get_all_stocks()
        logger.info(f"Total stocks to process: {len(all_stocks)}")
        
        # Test with first 10 stocks
        test_stocks = all_stocks[:10]
        
        filter_stats = {
            'total_processed': 0,
            'insufficient_data': 0,
            'cond_liquidity': 0,
            'cond_stage2': 0,
            'cond_breakout': 0,
            'cond_volume_confirm': 0,
            'cond_rs_uptrend': 0,
            'cond_strong_rs': 0,
            'cond_low_resistance': 0,
            'cond_not_overextended': 0,
            'all_passed': 0
        }
        
        for stock in test_stocks:
            symbol = stock['symbol']
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {symbol} - {stock['name']}")
            
            try:
                # Get daily data
                ohlcv_records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
                
                if not ohlcv_records or len(ohlcv_records) < 365:
                    logger.warning(f"  Insufficient data: {len(ohlcv_records) if ohlcv_records else 0} records")
                    filter_stats['insufficient_data'] += 1
                    continue
                
                # Convert to DataFrame
                daily_df = pd.DataFrame([{
                    'timestamp': r.timestamp,
                    'open': r.open,
                    'high': r.high,
                    'low': r.low,
                    'close': r.close,
                    'volume': r.volume
                } for r in ohlcv_records])
                
                # Filter out closed days
                daily_df = daily_df[daily_df['close'] > 0]
                logger.info(f"  Daily records (after filtering): {len(daily_df)}")
                
                if len(daily_df) < 365:
                    logger.warning(f"  Insufficient data after filtering")
                    filter_stats['insufficient_data'] += 1
                    continue
                
                # Convert to weekly
                daily_df['timestamp'] = pd.to_datetime(daily_df['timestamp'])
                weekly_df = resample_to_weekly(daily_df)
                logger.info(f"  Weekly records: {len(weekly_df)}")
                
                if len(weekly_df) < 52:
                    logger.warning(f"  Insufficient weekly data")
                    filter_stats['insufficient_data'] += 1
                    continue
                
                # Compute indicators
                weekly_df = compute_indicators(weekly_df, index_weekly)
                
                # Apply filters
                weekly_df = apply_filters(weekly_df, liquidity_threshold=1000000)
                
                filter_stats['total_processed'] += 1
                
                # Get latest week
                if len(weekly_df) > 0:
                    latest = weekly_df.iloc[-1]
                    
                    logger.info(f"  Latest week data:")
                    logger.info(f"    Close: ₹{latest['close']:.2f}")
                    logger.info(f"    MA30: ₹{latest['ma30']:.2f if pd.notna(latest['ma30']) else 'N/A'}")
                    logger.info(f"    MA30 Slope: {latest['ma30_slope']:.4f if pd.notna(latest['ma30_slope']) else 'N/A'}")
                    logger.info(f"    Volume: {latest['volume']:,}")
                    logger.info(f"    Avg Trading Value (20w): ₹{latest['avg_trading_value_20']:,.0f if pd.notna(latest['avg_trading_value_20']) else 'N/A'}")
                    logger.info(f"    RS: {latest['rs']:.4f if pd.notna(latest['rs']) else 'N/A'}")
                    logger.info(f"    52w High: ₹{latest['high_52w']:.2f if pd.notna(latest['high_52w']) else 'N/A'}")
                    
                    logger.info(f"  Filter Results:")
                    for cond in ['cond_liquidity', 'cond_stage2', 'cond_breakout', 'cond_volume_confirm',
                                'cond_rs_uptrend', 'cond_strong_rs', 'cond_low_resistance', 'cond_not_overextended']:
                        passed = bool(latest[cond])
                        logger.info(f"    {cond}: {'✓ PASS' if passed else '✗ FAIL'}")
                        if passed:
                            filter_stats[cond] += 1
                    
                    if latest['cond_all_passed']:
                        logger.info(f"  ✓✓✓ ALL CONDITIONS PASSED! ✓✓✓")
                        filter_stats['all_passed'] += 1
                    else:
                        logger.info(f"  ✗ Not all conditions passed")
                
            except Exception as e:
                logger.error(f"  Error processing {symbol}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("FILTER STATISTICS SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total stocks processed: {filter_stats['total_processed']}")
        logger.info(f"Insufficient data: {filter_stats['insufficient_data']}")
        logger.info(f"\nCondition Pass Rates:")
        for cond in ['cond_liquidity', 'cond_stage2', 'cond_breakout', 'cond_volume_confirm',
                    'cond_rs_uptrend', 'cond_strong_rs', 'cond_low_resistance', 'cond_not_overextended']:
            count = filter_stats[cond]
            pct = (count / filter_stats['total_processed'] * 100) if filter_stats['total_processed'] > 0 else 0
            logger.info(f"  {cond}: {count}/{filter_stats['total_processed']} ({pct:.1f}%)")
        
        logger.info(f"\nStocks passing ALL filters: {filter_stats['all_passed']}/{filter_stats['total_processed']}")

if __name__ == '__main__':
    debug_weinstein_screening()
