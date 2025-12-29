from flask import Blueprint, jsonify, request
from extensions import db
from models import OHLCV
from nifty500 import get_all_stocks, get_stock_by_symbol, get_stock_classification, is_nifty500_stock
from datetime import datetime, timedelta, timezone
import pandas as pd
import gc
import logging

# Set up logging
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

# Batch size for processing stocks
BATCH_SIZE = 50


def process_stock_analysis(stock, start_datetime, end_datetime):
    """
    Process analysis for a single stock. Returns dict or None.
    Optimized with explicit cleanup.
    """
    import pandas_ta as ta
    
    symbol = stock['symbol']
    
    # Filter: Only process Nifty 500 stocks
    if not (stock.get('nifty50', False) or 
           stock.get('nifty200', False) or 
           stock.get('nifty500', False)):
        return None
    
    # Get OHLCV data for the symbol (1 year)
    ohlcv_records = OHLCV.query.filter(
        OHLCV.symbol == symbol,
        OHLCV.timestamp >= start_datetime,
        OHLCV.timestamp <= end_datetime
    ).order_by(OHLCV.timestamp.asc()).all()
    
    if len(ohlcv_records) < 30:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame([{
        'timestamp': r.timestamp,
        'open': r.open,
        'high': r.high,
        'low': r.low,
        'close': r.close,
        'volume': r.volume
    } for r in ohlcv_records])
    
    # Clean up records
    del ohlcv_records
    
    if df.empty:
        return None
    
    # Filter out records where close = 0
    df = df[df['close'] > 0]
    
    if len(df) < 30:
        del df
        return None
    
    try:
        # Calculate indicators
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_21'] = ta.ema(df['close'], length=21)
        df['ema_44'] = ta.ema(df['close'], length=44)
        df['ema_200'] = ta.ema(df['close'], length=200)
        
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df['macd'] = macd[f'MACD_12_26_9']
            df['macd_signal'] = macd[f'MACDs_12_26_9']
            df['macd_hist'] = macd[f'MACDh_12_26_9']
        
        df['ema30'] = ta.ema(df['close'], length=30)
        df['ema30_slope'] = df['ema30'].diff()
        df['rsi_slope'] = df['rsi'].diff()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Determine MACD crossover
        macd_crossover = 'Neutral'
        if pd.notna(latest.get('macd')) and pd.notna(latest.get('macd_signal')):
            if pd.notna(prev.get('macd')) and pd.notna(prev.get('macd_signal')):
                if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
                    macd_crossover = 'Bullish'
                elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
                    macd_crossover = 'Bearish'
                elif latest['macd'] > latest['macd_signal']:
                    macd_crossover = 'Bullish'
                elif latest['macd'] < latest['macd_signal']:
                    macd_crossover = 'Bearish'
        
        # EMA crossovers
        ema_21_crossover = 'No'
        ema_44_crossover = 'No'
        ema_200_crossover = 'No'
        
        if pd.notna(latest.get('ema_21')) and pd.notna(prev.get('ema_21')):
            if latest['close'] > latest['ema_21'] and prev['close'] <= prev['ema_21']:
                ema_21_crossover = 'Yes'
            elif latest['close'] > latest['ema_21']:
                ema_21_crossover = 'Above'
        
        if pd.notna(latest.get('ema_44')) and pd.notna(prev.get('ema_44')):
            if latest['close'] > latest['ema_44'] and prev['close'] <= prev['ema_44']:
                ema_44_crossover = 'Yes'
            elif latest['close'] > latest['ema_44']:
                ema_44_crossover = 'Above'
        
        if pd.notna(latest.get('ema_200')) and pd.notna(prev.get('ema_200')):
            if latest['close'] > latest['ema_200'] and prev['close'] <= prev['ema_200']:
                ema_200_crossover = 'Yes'
            elif latest['close'] > latest['ema_200']:
                ema_200_crossover = 'Above'
        
        # Calculate score
        score = 0
        
        if pd.notna(latest.get('ema30')) and pd.notna(latest.get('ema30_slope')):
            if latest['close'] > latest['ema30'] and latest['ema30_slope'] > 1.0:
                score += 15
        
        if pd.notna(latest['rsi']):
            rsi = latest['rsi']
            if 20 <= rsi < 30:
                score += 20
            elif 30 <= rsi < 40:
                score += 15
            elif 40 <= rsi < 50:
                score += 10
            elif 50 <= rsi < 60:
                score += 5
            elif 60 <= rsi <= 80:
                score += 2
        
        if pd.notna(latest.get('ema30')) and latest['ema30'] > 0:
            extension = (latest['close'] - latest['ema30']) / latest['ema30']
            if extension <= 0.15:
                score += 15
        
        if pd.notna(latest.get('rsi_slope')):
            if latest['rsi_slope'] > 0:
                score += 10
        
        if pd.notna(latest.get('macd')) and pd.notna(latest.get('macd_signal')):
            if latest['macd'] > latest['macd_signal']:
                score += 15
        
        crossover_score = 0
        if len(df) >= 4:
            for i in range(1, 4):
                curr = df.iloc[-i]
                prev_day = df.iloc[-i-1]
                
                if (pd.notna(curr.get('macd')) and pd.notna(curr.get('macd_signal')) and
                    pd.notna(prev_day.get('macd')) and pd.notna(prev_day.get('macd_signal'))):
                    if (curr['macd'] > curr['macd_signal'] and 
                        prev_day['macd'] <= prev_day['macd_signal']):
                        if i == 1:
                            crossover_score = 10
                        elif i == 2:
                            crossover_score = 7
                        else:
                            crossover_score = 5
                        break
        score += crossover_score
        
        result = {
            'symbol': symbol,
            'name': stock['name'],
            'sector': stock.get('sector', 'N/A'),
            'classification': get_stock_classification(symbol),
            'score': score,
            'rsi': round(float(latest['rsi']), 2) if pd.notna(latest['rsi']) else None,
            'macd_signal': macd_crossover,
            'ema_crossover_21_44': ema_21_crossover if ema_21_crossover == 'Yes' else ('Above' if ema_44_crossover == 'Above' or ema_21_crossover == 'Above' else 'No'),
            'price_above_ema_200': ema_200_crossover,
            'current_price': float(latest['close'])
        }
        
        # Cleanup
        del df
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating indicators for {symbol}: {str(e)}")
        return None


@analysis_bp.route('/api/analysis/stocks', methods=['GET'])
def get_analysis_data():
    """Get technical analysis data for Nifty 500 stocks only"""
    try:
        end_datetime = datetime.now(timezone.utc) + timedelta(days=1)
        start_datetime = end_datetime - timedelta(days=366)
        
        stocks = get_all_stocks()
        analysis_data = []
        total_stocks = len(stocks)
        
        # Process in batches
        for batch_start in range(0, total_stocks, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_stocks)
            batch_stocks = stocks[batch_start:batch_end]
            
            for stock in batch_stocks:
                result = process_stock_analysis(stock, start_datetime, end_datetime)
                if result:
                    analysis_data.append(result)
            
            # Force garbage collection after each batch
            gc.collect()
        
        logger.info(f"Analysis completed: {len(analysis_data)} stocks processed out of {total_stocks} total stocks")
        
        return jsonify({
            'analysis_data': analysis_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_stocks': len(analysis_data),
            'total_in_universe': total_stocks
        })
        
    except Exception as e:
        logger.error(f"Error in get_analysis_data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/api/analysis/chart/<symbol>', methods=['GET'])
def get_chart_data(symbol):
    """Get detailed chart data with indicators for a specific stock"""
    try:
        import pandas_ta as ta
        
        ohlcv_records = OHLCV.query.filter(
            OHLCV.symbol == symbol
        ).order_by(OHLCV.timestamp.asc()).all()
        
        if not ohlcv_records:
            return jsonify({'error': 'No data found for this symbol'}), 404
        
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume
        } for r in ohlcv_records])
        
        del ohlcv_records
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        df_daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        del df
        
        df_daily.reset_index(inplace=True)
        df_daily = df_daily[df_daily['close'] > 0]
        
        if len(df_daily) < 30:
            return jsonify({'error': 'Insufficient data for analysis'}), 404
        
        df_daily['rsi'] = ta.rsi(df_daily['close'], length=14)
        df_daily['ema_21'] = ta.ema(df_daily['close'], length=21)
        df_daily['ema_44'] = ta.ema(df_daily['close'], length=44)
        df_daily['ema_200'] = ta.ema(df_daily['close'], length=200)
        
        macd = ta.macd(df_daily['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df_daily['macd'] = macd[f'MACD_12_26_9']
            df_daily['macd_signal'] = macd[f'MACDs_12_26_9']
            df_daily['macd_hist'] = macd[f'MACDh_12_26_9']
        
        chart_data = []
        for _, row in df_daily.iterrows():
            chart_data.append({
                'timestamp': row['timestamp'].isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'rsi': float(row['rsi']) if pd.notna(row['rsi']) else None,
                'ema_21': float(row['ema_21']) if pd.notna(row['ema_21']) else None,
                'ema_44': float(row['ema_44']) if pd.notna(row['ema_44']) else None,
                'ema_200': float(row['ema_200']) if pd.notna(row['ema_200']) else None,
                'macd': float(row['macd']) if pd.notna(row.get('macd')) else None,
                'macd_signal': float(row['macd_signal']) if pd.notna(row.get('macd_signal')) else None,
                'macd_hist': float(row['macd_hist']) if pd.notna(row.get('macd_hist')) else None
            })
        
        stock_info = get_stock_by_symbol(symbol)
        
        del df_daily
        gc.collect()
        
        return jsonify({
            'symbol': symbol,
            'name': stock_info['name'] if stock_info else symbol,
            'sector': stock_info.get('sector', 'N/A') if stock_info else 'N/A',
            'chart_data': chart_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in get_chart_data for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500
