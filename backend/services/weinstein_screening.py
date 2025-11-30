"""
Weinstein Stock Screening Module

Implements Stan Weinstein's Stage Analysis methodology for stock screening.
Processes daily OHLCV data, converts to weekly timeframes, calculates technical
indicators, and applies 8 filter conditions to identify Stage 2 breakout candidates.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from extensions import db
from models import OHLCV
from nifty500 import get_all_stocks, get_nifty50_stocks
import logging

logger = logging.getLogger(__name__)


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
    
    Args:
        df: DataFrame with columns [timestamp, close]
           timestamp should be datetime index
    
    Returns:
        DataFrame with weekly index close prices
    """
    if df.empty:
        return df
    
    # Ensure timestamp is datetime index
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')
    
    # Resample to weekly (week ending on Friday)
    weekly = df.resample('W-FRI').agg({
        'close': 'last'  # Last close of the week
    }).dropna()
    
    # Reset index
    weekly.reset_index(inplace=True)
    
    return weekly


def compute_indicators(df, index_df):
    """
    Compute all required Weinstein indicators on weekly data.
    
    Args:
        df: Weekly OHLCV DataFrame for a stock
        index_df: Weekly index close DataFrame
    
    Returns:
        DataFrame with additional indicator columns
    """
    if df.empty or len(df) < 52:  # Need at least 52 weeks for calculations
        return df
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # 1. 30-week moving average of close
    df['ma30'] = df['close'].rolling(window=30, min_periods=30).mean()
    
    # 2. Slope of MA30 (current MA30 - previous MA30)
    df['ma30_slope'] = df['ma30'].diff()
    
    # 3. 52-week high of price
    df['high_52w'] = df['high'].rolling(window=52, min_periods=52).max()
    
    # 4. 10-week average volume
    df['avg_vol_10'] = df['volume'].rolling(window=10, min_periods=10).mean()
    
    # 5. Trading value = close × volume
    df['trading_value'] = df['close'] * df['volume']
    
    # 6. 20-week average trading value
    df['avg_trading_value_20'] = df['trading_value'].rolling(window=20, min_periods=20).mean()
    
    # 7. Relative Strength (RS) = stock_close / index_close
    # Merge with index data on timestamp
    df = df.merge(index_df[['timestamp', 'close']], on='timestamp', how='left', suffixes=('', '_index'))
    df.rename(columns={'close_index': 'index_close'}, inplace=True)
    
    # Calculate RS
    df['rs'] = df['close'] / df['index_close']
    
    # 8. RS slope = change in RS vs previous week
    df['rs_slope'] = df['rs'].diff()
    
    # 9. 52-week high of RS
    df['rs_52w_high'] = df['rs'].rolling(window=52, min_periods=52).max()
    
    # 10. RSI (14-week) for scoring
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=14).mean()
    rs_rsi = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs_rsi))
    
    return df


def apply_filters(df, liquidity_threshold=1000000):
    """
    Apply Weinstein filter conditions to weekly data.
    
    Args:
        df: DataFrame with computed indicators
        liquidity_threshold: Minimum 20-week avg trading value (default: ₹1,000,000)
    
    Returns:
        DataFrame with boolean filter columns
    """
    if df.empty:
        return df
    
    # Initialize all condition columns as False
    df['cond_liquidity'] = False
    df['cond_stage2'] = False
    df['cond_breakout'] = False
    df['cond_volume_confirm'] = False
    df['cond_rs_uptrend'] = False
    df['cond_strong_rs'] = False
    df['cond_low_resistance'] = False
    df['cond_not_overextended'] = False
    df['cond_all_passed'] = False
    
    # Need at least 2 rows for previous week comparisons
    if len(df) < 2:
        return df
    
    # Apply conditions row by row (starting from index 1 to have previous week)
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        
        # a. Liquidity condition
        if pd.notna(row['avg_trading_value_20']):
            df.loc[i, 'cond_liquidity'] = row['avg_trading_value_20'] > liquidity_threshold
        
        # b. Stage-2 condition: close > MA30 AND MA30 slope > 0 (stricter: slope must be > 1.0)
        if pd.notna(row['ma30']) and pd.notna(row['ma30_slope']):
            df.loc[i, 'cond_stage2'] = (row['close'] > row['ma30']) and (row['ma30_slope'] > 1.0)
        
        # c. Breakout condition: close > previous 52-week high × 1.01 (stricter: 1% instead of 0.5%)
        if pd.notna(prev_row['high_52w']):
            df.loc[i, 'cond_breakout'] = row['close'] > (prev_row['high_52w'] * 1.01)
        
        # d. Volume confirmation: volume ≥ 1.3 × previous week's avg_vol_10 (stricter: 1.3x instead of 1.2x)
        if pd.notna(prev_row['avg_vol_10']):
            df.loc[i, 'cond_volume_confirm'] = row['volume'] >= (1.3 * prev_row['avg_vol_10'])
        
        # e. RS uptrend: RS slope > 0 AND RS > previous week's RS
        if pd.notna(row['rs_slope']) and pd.notna(prev_row['rs']):
            df.loc[i, 'cond_rs_uptrend'] = (row['rs_slope'] > 0) and (row['rs'] > prev_row['rs'])
        
        # f. Strong RS: RS ≥ 92% of RS 52-week high (stricter: 92% instead of 90%)
        if pd.notna(row['rs']) and pd.notna(row['rs_52w_high']) and row['rs_52w_high'] > 0:
            df.loc[i, 'cond_strong_rs'] = row['rs'] >= (0.92 * row['rs_52w_high'])
        
        # g. Low overhead resistance: close ≥ 96% of current 52-week high (stricter: 96% instead of 95%)
        if pd.notna(row['high_52w']) and row['high_52w'] > 0:
            df.loc[i, 'cond_low_resistance'] = row['close'] >= (0.96 * row['high_52w'])
        
        # h. Not overextended: (close - MA30) / MA30 ≤ 0.25 (stricter: 25% instead of 35%)
        if pd.notna(row['ma30']) and row['ma30'] > 0:
            extension = (row['close'] - row['ma30']) / row['ma30']
            df.loc[i, 'cond_not_overextended'] = extension <= 0.25
        
        # Check if all conditions passed
        df.loc[i, 'cond_all_passed'] = (
            df.loc[i, 'cond_liquidity'] and
            df.loc[i, 'cond_stage2'] and
            df.loc[i, 'cond_breakout'] and
            df.loc[i, 'cond_volume_confirm'] and
            df.loc[i, 'cond_rs_uptrend'] and
            df.loc[i, 'cond_strong_rs'] and
            df.loc[i, 'cond_low_resistance'] and
            df.loc[i, 'cond_not_overextended']
        )
    
    return df


def get_or_create_index_data():
    """
    Get NIFTY 50 index data from database or create synthetic index.
    
    Returns:
        DataFrame with columns [timestamp, close]
    """
    # Try to fetch NIFTY 50 index data (common symbols: ^NSEI, NIFTY50, etc.)
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
    
    # If no index data found, create synthetic index from available stocks
    logger.warning("No index data found in database. Creating synthetic index from available stocks.")
    
    # Get Nifty 50 stocks and try to match with database symbols
    nifty50_stocks = get_nifty50_stocks()
    nifty50_symbols = [s['symbol'] for s in nifty50_stocks]
    
    # Try both with and without .NS suffix
    symbols_to_try = []
    for sym in nifty50_symbols[:20]:  # Use top 20
        symbols_to_try.append(sym)
        if not sym.endswith('.NS'):
            symbols_to_try.append(f"{sym}.NS")
    
    # Get all OHLCV data for available symbols
    all_data = []
    for symbol in symbols_to_try:
        records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
        if records:
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'symbol': r.symbol,
                'close': r.close
            } for r in records])
            all_data.append(df)
            if len(all_data) >= 10:  # Stop after finding 10 stocks
                break
    
    # If still no data, use ANY available stocks from database
    if not all_data:
        logger.warning("No Nifty 50 stocks found. Using any available stocks for synthetic index.")
        # Get first 10 symbols from database
        available_symbols = db.session.query(OHLCV.symbol).distinct().limit(10).all()
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
    
    # Combine all data and calculate average close for each timestamp
    combined = pd.concat(all_data, ignore_index=True)
    synthetic_index = combined.groupby('timestamp')['close'].mean().reset_index()
    
    logger.info(f"Created synthetic index from {len(all_data)} stocks")
    
    return synthetic_index



def generate_shortlist_for_latest_week(processed_df):
    """
    Generate shortlist of stocks that passed all conditions in the latest week.
    
    Args:
        processed_df: DataFrame with all stocks and their weekly data
    
    Returns:
        List of symbols that passed all conditions
    """
    if processed_df.empty:
        return []
    
    # Get the latest week's data
    latest_week = processed_df['timestamp'].max()
    latest_data = processed_df[processed_df['timestamp'] == latest_week]
    
    # Filter stocks where all conditions passed
    shortlist = latest_data[latest_data['cond_all_passed'] == True]['symbol'].unique().tolist()
    
    return shortlist


def run_weinstein_screening(liquidity_threshold=1000000):
    """
    Main function to run Weinstein screening on all Nifty 500 stocks.
    
    Args:
        liquidity_threshold: Minimum 20-week avg trading value (default: ₹1,000,000)
    
    Returns:
        tuple: (shortlist, processed_df)
            - shortlist: List of symbols passing all filters
            - processed_df: Full DataFrame with all stocks and indicators
    """
    logger.info("Starting Weinstein screening process...")
    
    # Get all Nifty 500 stocks
    all_stocks = get_all_stocks()
    stock_info_map = {s['symbol']: s for s in all_stocks}
    
    # Get or create index data
    index_daily = get_or_create_index_data()
    
    if index_daily.empty:
        logger.error("No index data available. Cannot proceed with screening.")
        return [], pd.DataFrame()
    
    # Convert index to weekly
    index_daily['timestamp'] = pd.to_datetime(index_daily['timestamp'])
    index_weekly = resample_index_to_weekly(index_daily)
    
    logger.info(f"Processing {len(all_stocks)} stocks...")
    
    all_processed_data = []
    
    for i, stock in enumerate(all_stocks):
        symbol = stock['symbol']
        
        # Log progress every 50 stocks
        if (i + 1) % 50 == 0:
            logger.info(f"Processed {i + 1}/{len(all_stocks)} stocks...")
        
        try:
            # Get daily OHLCV data for the stock
            ohlcv_records = OHLCV.query.filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).all()
            
            if not ohlcv_records or len(ohlcv_records) < 365:  # Need at least 1 year of daily data
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
            
            # Filter out records where close = 0 (market closed)
            daily_df = daily_df[daily_df['close'] > 0]
            
            if len(daily_df) < 365:
                continue
            
            # Convert timestamp to datetime
            daily_df['timestamp'] = pd.to_datetime(daily_df['timestamp'])
            
            # Resample to weekly
            weekly_df = resample_to_weekly(daily_df)
            
            if len(weekly_df) < 52:  # Need at least 52 weeks
                continue
            
            # Compute indicators
            weekly_df = compute_indicators(weekly_df, index_weekly)
            
            # Apply filters
            weekly_df = apply_filters(weekly_df, liquidity_threshold)
            
            # Add symbol and stock info
            weekly_df['symbol'] = symbol
            weekly_df['name'] = stock.get('name', symbol)
            weekly_df['sector'] = stock.get('sector', 'N/A')
            
            all_processed_data.append(weekly_df)
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")
            continue
    
    # Combine all processed data
    if not all_processed_data:
        logger.warning("No stocks were successfully processed")
        return [], pd.DataFrame()
    
    processed_df = pd.concat(all_processed_data, ignore_index=True)
    
    # Generate shortlist for latest week
    shortlist = generate_shortlist_for_latest_week(processed_df)
    
    logger.info(f"Weinstein screening complete. {len(shortlist)} stocks passed all filters.")
    
    return shortlist, processed_df


def get_weinstein_scores_for_latest_week(liquidity_threshold=1000000):
    """
    Get Weinstein scores and details for all stocks in the latest week.
    Suitable for API response.
    
    Args:
        liquidity_threshold: Minimum 20-week avg trading value
    
    Returns:
        List of dicts with stock details and scores
    """
    shortlist, processed_df = run_weinstein_screening(liquidity_threshold)
    
    if processed_df.empty:
        return []
    
    # Get latest week data
    latest_week = processed_df['timestamp'].max()
    latest_data = processed_df[processed_df['timestamp'] == latest_week].copy()
    
    # Calculate enhanced score (0-100) based on conditions + proximity + RSI
    condition_cols = [
        'cond_liquidity', 'cond_stage2', 'cond_breakout', 'cond_volume_confirm',
        'cond_rs_uptrend', 'cond_strong_rs', 'cond_low_resistance', 'cond_not_overextended'
    ]
    
    # Base score from conditions (8 conditions × 10 points = 80 points max)
    latest_data['base_score'] = latest_data[condition_cols].sum(axis=1) * 10
    
    # Bonus points for proximity to breakout (0-10 points)
    # Closer to 52-week high = higher score
    def calculate_breakout_bonus(row):
        if pd.notna(row['close']) and pd.notna(row['high_52w']) and row['high_52w'] > 0:
            proximity = (row['close'] / row['high_52w']) * 100  # Percentage of 52w high
            if proximity >= 99:
                return 10  # Very close to breakout
            elif proximity >= 97:
                return 7
            elif proximity >= 95:
                return 5
            elif proximity >= 92:
                return 3
            else:
                return 0
        return 0
    
    latest_data['breakout_bonus'] = latest_data.apply(calculate_breakout_bonus, axis=1)
    
    # Bonus points for lower RSI (0-10 points)
    # Lower RSI = more room to run = higher score
    def calculate_rsi_bonus(row):
        if pd.notna(row['rsi']):
            if row['rsi'] < 30:
                return 10  # Oversold - excellent
            elif row['rsi'] < 40:
                return 8
            elif row['rsi'] < 50:
                return 6
            elif row['rsi'] < 60:
                return 4
            elif row['rsi'] < 70:
                return 2
            else:
                return 0  # Overbought - no bonus
        return 0
    
    latest_data['rsi_bonus'] = latest_data.apply(calculate_rsi_bonus, axis=1)
    
    # Total score = base + breakout proximity + RSI bonus (max 100)
    latest_data['score'] = (latest_data['base_score'] + 
                            latest_data['breakout_bonus'] + 
                            latest_data['rsi_bonus']).clip(upper=100)
    
    # Determine stage based on conditions (stricter classification)
    def determine_stage(row):
        if row['cond_all_passed']:
            return 'Stage 2'
        elif row['cond_stage2'] and row['cond_rs_uptrend']:
            return 'Stage 2'  # In Stage 2 but not all conditions met
        elif pd.notna(row['ma30']) and row['close'] < row['ma30'] and pd.notna(row['ma30_slope']) and row['ma30_slope'] < -1.0:
            return 'Stage 4'  # Declining with negative slope
        elif pd.notna(row['ma30']) and row['close'] < row['ma30']:
            return 'Stage 1'  # Below MA30, potentially basing
        else:
            return 'Stage 3'  # Distribution/topping
    
    latest_data['stage'] = latest_data.apply(determine_stage, axis=1)
    
    # Calculate price change (current vs 1 week ago)
    latest_data['change'] = 0.0
    for symbol in latest_data['symbol'].unique():
        symbol_data = processed_df[processed_df['symbol'] == symbol].sort_values('timestamp')
        if len(symbol_data) >= 2:
            current_price = symbol_data.iloc[-1]['close']
            prev_price = symbol_data.iloc[-2]['close']
            if prev_price > 0:
                change_pct = ((current_price - prev_price) / prev_price) * 100
                latest_data.loc[latest_data['symbol'] == symbol, 'change'] = change_pct
    
    # Prepare response
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
            'ma150': None,  # Not calculated in weekly (would need ~150 weeks)
            'ma200': None,  # Not calculated in weekly (would need ~200 weeks)
            'rs': round(float(row['rs']), 4) if pd.notna(row['rs']) else None,
            'conditions_passed': {
                'liquidity': bool(row['cond_liquidity']),
                'stage2': bool(row['cond_stage2']),
                'breakout': bool(row['cond_breakout']),
                'volume_confirm': bool(row['cond_volume_confirm']),
                'rs_uptrend': bool(row['cond_rs_uptrend']),
                'strong_rs': bool(row['cond_strong_rs']),
                'low_resistance': bool(row['cond_low_resistance']),
                'not_overextended': bool(row['cond_not_overextended'])
            }
        })
    
    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results
