"""
Weinstein Stock Screening Module

Implements Stan Weinstein's Stage Analysis methodology for stock screening.
Processes daily OHLCV data, converts to weekly timeframes, calculates technical
indicators, and applies 3 core filter conditions to identify Stage 2 breakout candidates.
Optimized with batch processing for reduced memory usage.
"""

import pandas as pd
import numpy as np
import gc
from datetime import datetime, timezone
from extensions import db
from models import OHLCV
from nifty500 import get_all_stocks, get_nifty50_stocks
import logging

logger = logging.getLogger(__name__)

# Batch size for processing
BATCH_SIZE = 50


def resample_to_weekly(df):
    """
    Convert daily OHLCV data to weekly OHLCV.
    
    Args:
        df: DataFrame with columns [timestamp, open, high, low, close, volume]
           timestamp should be datetime index
    
    Returns:
        DataFrame with weekly OHLCV data
    """
    if df.empty:
        return df
    
    # Ensure timestamp is datetime index
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')
    
    # Resample to weekly (week ending on Friday)
    weekly = df.resample('W-FRI').agg({
        'open': 'first',    # First open of the week
        'high': 'max',      # Highest high of the week
        'low': 'min',       # Lowest low of the week
        'close': 'last',    # Last close of the week
        'volume': 'sum'     # Sum of all volumes
    }).dropna()
    
    # Reset index to have timestamp as column
    weekly.reset_index(inplace=True)
    
    return weekly


def resample_index_to_weekly(df):
    """
    Convert daily index data to weekly close prices.
    """
    if df.empty:
        return df
    
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')
    
    weekly = df.resample('W-FRI').agg({
        'close': 'last'
    }).dropna()
    
    weekly.reset_index(inplace=True)
    
    return weekly


def compute_indicators(df, index_df):
    """
    Compute all required Weinstein indicators on weekly data.
    """
    if df.empty or len(df) < 52:
        return df
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # 1. 30-week moving average of close
    df['ma30'] = df['close'].rolling(window=30, min_periods=30).mean()
    
    # 2. Slope of MA30
    df['ma30_slope'] = df['ma30'].diff()
    
    # 3. 52-week high of price
    df['high_52w'] = df['high'].rolling(window=52, min_periods=52).max()
    
    # 4. 10-week average volume
    df['avg_vol_10'] = df['volume'].rolling(window=10, min_periods=10).mean()
    
    # 5. Trading value
    df['trading_value'] = df['close'] * df['volume']
    
    # 6. 20-week average trading value
    df['avg_trading_value_20'] = df['trading_value'].rolling(window=20, min_periods=20).mean()
    
    # 7. Relative Strength
    df = df.merge(index_df[['timestamp', 'close']], on='timestamp', how='left', suffixes=('', '_index'))
    df.rename(columns={'close_index': 'index_close'}, inplace=True)
    
    df['rs'] = df['close'] / df['index_close']
    df['rs_slope'] = df['rs'].diff()
    df['rs_52w_high'] = df['rs'].rolling(window=52, min_periods=52).max()
    
    # RSI (14-week)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=14).mean()
    rs_rsi = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs_rsi))
    df['rsi_slope'] = df['rsi'].diff()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    return df


def apply_filters(df, liquidity_threshold=None):
    """
    Apply Weinstein filter conditions to weekly data.
    """
    if df.empty:
        return df
    
    df['cond_stage2'] = False
    df['cond_low_resistance'] = False
    df['cond_not_overextended'] = False
    df['cond_all_passed'] = False
    
    if len(df) < 2:
        return df
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        
        # 1. Stage-2 condition
        if pd.notna(row['ma30']) and pd.notna(row['ma30_slope']):
            df.loc[i, 'cond_stage2'] = (row['close'] > row['ma30']) and (row['ma30_slope'] > 0)
        
        # 2. Low overhead resistance
        if pd.notna(row['high_52w']) and row['high_52w'] > 0:
            df.loc[i, 'cond_low_resistance'] = row['close'] >= (0.98 * row['high_52w'])
        
        # 3. Not overextended
        if pd.notna(row['ma30']) and row['ma30'] > 0:
            extension = (row['close'] - row['ma30']) / row['ma30']
            df.loc[i, 'cond_not_overextended'] = extension <= 0.20
        
        df.loc[i, 'cond_all_passed'] = (
            df.loc[i, 'cond_stage2'] and
            df.loc[i, 'cond_low_resistance'] and
            df.loc[i, 'cond_not_overextended']
        )
    
    return df


def get_or_create_index_data():
    """
    Get NIFTY 50 index data from database or create synthetic index.
    Optimized to limit data fetched.
    """
    index_symbols = ['^NSEI', 'NIFTY50', 'NIFTY 50', 'NSEI', '^NSEI.NS', 'NIFTY50.NS']
    
    for symbol in index_symbols:
        index_records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
        if index_records:
            logger.info(f"Using index data from symbol: {symbol}")
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'close': r.close
            } for r in index_records])
            return df
    
    logger.warning("No index data found. Creating synthetic index from available stocks.")
    
    # Get first 10 available symbols for synthetic index
    available_symbols = db.session.query(OHLCV.symbol).distinct().limit(10).all()
    all_data = []
    
    for (symbol,) in available_symbols:
        records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
        if records:
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'symbol': r.symbol,
                'close': r.close
            } for r in records])
            all_data.append(df)
    
    if not all_data:
        logger.error("No data available to create synthetic index")
        return pd.DataFrame(columns=['timestamp', 'close'])
    
    combined = pd.concat(all_data, ignore_index=True)
    synthetic_index = combined.groupby('timestamp')['close'].mean().reset_index()
    
    logger.info(f"Created synthetic index from {len(all_data)} stocks")
    
    return synthetic_index


def process_stock_batch(stocks, index_weekly, liquidity_threshold=None):
    """
    Process a batch of stocks and return their processed DataFrames.
    Includes memory cleanup after processing.
    """
    batch_results = []
    
    for stock in stocks:
        symbol = stock['symbol']
        
        try:
            # Get daily OHLCV data - use yield_per for memory efficiency
            ohlcv_records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
            
            if not ohlcv_records or len(ohlcv_records) < 365:
                continue
            
            daily_df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume
            } for r in ohlcv_records])
            
            # Clean up records immediately
            del ohlcv_records
            
            daily_df = daily_df[daily_df['close'] > 0]
            
            if len(daily_df) < 365:
                del daily_df
                continue
            
            daily_df['timestamp'] = pd.to_datetime(daily_df['timestamp'])
            weekly_df = resample_to_weekly(daily_df)
            
            # Clean up daily data
            del daily_df
            
            if len(weekly_df) < 52:
                del weekly_df
                continue
            
            weekly_df = compute_indicators(weekly_df, index_weekly)
            weekly_df = apply_filters(weekly_df, liquidity_threshold)
            
            weekly_df['symbol'] = symbol
            weekly_df['name'] = stock.get('name', symbol)
            weekly_df['sector'] = stock.get('sector', 'N/A')
            
            # Only keep the last row for memory efficiency in final results
            latest_week_df = weekly_df.tail(1).copy()
            batch_results.append(latest_week_df)
            
            del weekly_df
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")
            continue
    
    return batch_results


def run_weinstein_screening(liquidity_threshold=1000000):
    """
    Main function to run Weinstein screening on all Nifty 500 stocks.
    Optimized with batch processing for reduced memory usage.
    """
    logger.info("Starting Weinstein screening process...")
    
    all_stocks = get_all_stocks()
    
    index_daily = get_or_create_index_data()
    
    if index_daily.empty:
        logger.error("No index data available. Cannot proceed with screening.")
        return [], pd.DataFrame()
    
    index_daily['timestamp'] = pd.to_datetime(index_daily['timestamp'])
    index_weekly = resample_index_to_weekly(index_daily)
    
    del index_daily
    gc.collect()
    
    logger.info(f"Processing {len(all_stocks)} stocks in batches of {BATCH_SIZE}...")
    
    all_latest_data = []
    total_stocks = len(all_stocks)
    
    # Process in batches
    for batch_start in range(0, total_stocks, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_stocks)
        batch_stocks = all_stocks[batch_start:batch_end]
        
        logger.info(f"Processing batch {batch_start + 1}-{batch_end} of {total_stocks}...")
        
        batch_results = process_stock_batch(batch_stocks, index_weekly, liquidity_threshold)
        all_latest_data.extend(batch_results)
        
        # Force garbage collection after each batch
        gc.collect()
    
    if not all_latest_data:
        logger.warning("No stocks were successfully processed")
        return [], pd.DataFrame()
    
    processed_df = pd.concat(all_latest_data, ignore_index=True)
    
    # Generate shortlist
    shortlist = processed_df[processed_df['cond_all_passed'] == True]['symbol'].unique().tolist()
    
    logger.info(f"Weinstein screening complete. {len(shortlist)} stocks passed all filters.")
    
    return shortlist, processed_df


def get_weinstein_scores_for_latest_week(liquidity_threshold=None):
    """
    Get Weinstein scores and details for all stocks in the latest week.
    """
    shortlist, processed_df = run_weinstein_screening(liquidity_threshold)
    
    if processed_df.empty:
        return []
    
    latest_data = processed_df.copy()
    
    # Calculate score
    latest_data['score'] = (
        (latest_data['cond_stage2'].astype(int) * 33.33) +
        (latest_data['cond_low_resistance'].astype(int) * 33.33) +
        (latest_data['cond_not_overextended'].astype(int) * 33.34)
    ).round(0).astype(int)
    
    def determine_stage(row):
        if row['cond_all_passed']:
            return 'Stage 2'
        elif row['cond_stage2']:
            return 'Stage 2'
        elif pd.notna(row['ma30']) and row['close'] < row['ma30'] and pd.notna(row['ma30_slope']) and row['ma30_slope'] < -1.0:
            return 'Stage 4'
        elif pd.notna(row['ma30']) and row['close'] < row['ma30']:
            return 'Stage 1'
        else:
            return 'Stage 3'
    
    latest_data['stage'] = latest_data.apply(determine_stage, axis=1)
    latest_data['change'] = 0.0
    
    results = []
    for _, row in latest_data.iterrows():
        results.append({
            'symbol': row['symbol'],
            'name': row['name'],
            'sector': row['sector'],
            'score': int(row['score']),
            'stage': row['stage'],
            'price': round(float(row['close']), 2),
            'change': round(float(row['change']), 2),
            'volume': int(row['volume']),
            'ma30': round(float(row['ma30']), 2) if pd.notna(row['ma30']) else None,
            'ma150': None,
            'ma200': None,
            'rs': round(float(row['rs']), 4) if pd.notna(row['rs']) else None,
            'conditions_passed': {
                'stage2': bool(row['cond_stage2']),
                'low_resistance': bool(row['cond_low_resistance']),
                'not_overextended': bool(row['cond_not_overextended'])
            }
        })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results
