"""
Simple debug script to check filter logic
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

def simple_debug():
    """Simple debug to check one stock"""
    
    with app.app_context():
        logger.info("Getting index data...")
        index_daily = get_or_create_index_data()
        
        if index_daily.empty:
            logger.error("No index data")
            return
        
        logger.info(f"Index data: {len(index_daily)} records")
        
        index_daily['timestamp'] = pd.to_datetime(index_daily['timestamp'])
        index_weekly = resample_index_to_weekly(index_daily)
        logger.info(f"Index weekly: {len(index_weekly)} weeks")
        
        # Test with one stock
        symbol = "RELIANCE.NS"
        logger.info(f"\nProcessing {symbol}...")
        
        records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
        logger.info(f"Daily records: {len(records)}")
        
        daily_df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume
        } for r in records])
        
        daily_df = daily_df[daily_df['close'] > 0]
        daily_df['timestamp'] = pd.to_datetime(daily_df['timestamp'])
        
        weekly_df = resample_to_weekly(daily_df)
        logger.info(f"Weekly records: {len(weekly_df)}")
        
        weekly_df = compute_indicators(weekly_df, index_weekly)
        logger.info(f"After indicators: {len(weekly_df)} weeks")
        
        # Check latest week before filters
        latest = weekly_df.iloc[-1]
        logger.info(f"\nLatest week BEFORE filters:")
        logger.info(f"  Close: {latest['close']:.2f}")
        ma30_val = f"{latest['ma30']:.2f}" if pd.notna(latest['ma30']) else 'N/A'
        logger.info(f"  MA30: {ma30_val}")
        ma30_slope_val = f"{latest['ma30_slope']:.4f}" if pd.notna(latest['ma30_slope']) else 'N/A'
        logger.info(f"  MA30 Slope: {ma30_slope_val}")
        logger.info(f"  Volume: {latest['volume']:,.0f}")
        avg_tv_val = f"{latest['avg_trading_value_20']:,.0f}" if pd.notna(latest['avg_trading_value_20']) else 'N/A'
        logger.info(f"  Avg Trading Value 20: {avg_tv_val}")
        rs_val = f"{latest['rs']:.4f}" if pd.notna(latest['rs']) else 'N/A'
        logger.info(f"  RS: {rs_val}")
        high_52w_val = f"{latest['high_52w']:.2f}" if pd.notna(latest['high_52w']) else 'N/A'
        logger.info(f"  52w High: {high_52w_val}")
        
        weekly_df = apply_filters(weekly_df, liquidity_threshold=1000000)
        
        # Check latest week after filters
        latest = weekly_df.iloc[-1]
        logger.info(f"\nLatest week AFTER filters:")
        for cond in ['cond_liquidity', 'cond_stage2', 'cond_breakout', 'cond_volume_confirm',
                    'cond_rs_uptrend', 'cond_strong_rs', 'cond_low_resistance', 'cond_not_overextended']:
            logger.info(f"  {cond}: {latest[cond]}")
        
        logger.info(f"  All passed: {latest['cond_all_passed']}")
        
        # Count how many weeks pass each filter
        logger.info(f"\nFilter pass counts across all weeks:")
        for cond in ['cond_liquidity', 'cond_stage2', 'cond_breakout', 'cond_volume_confirm',
                    'cond_rs_uptrend', 'cond_strong_rs', 'cond_low_resistance', 'cond_not_overextended']:
            count = weekly_df[cond].sum()
            logger.info(f"  {cond}: {count}/{len(weekly_df)}")

if __name__ == '__main__':
    simple_debug()
