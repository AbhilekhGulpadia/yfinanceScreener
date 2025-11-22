from flask import Blueprint, jsonify, request
from extensions import db
from models import OHLCV
from nifty500 import get_all_stocks, get_stock_by_symbol
from datetime import datetime, timedelta, timezone
import pandas as pd
import logging

# Set up logging
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/api/analysis/stocks', methods=['GET'])
def get_analysis_data():
    """Get technical analysis data for all stocks with indicators based on 1 year of data"""
    try:
        import pandas_ta as ta
        
        # Use minimum 1 year of historical data for analysis
        # Use current time + 1 day to ensure we include latest data even if there are minor timezone diffs
        end_datetime = datetime.now(timezone.utc) + timedelta(days=1)
        start_datetime = end_datetime - timedelta(days=366)  # 1 year of data
        
        # Get all stocks
        stocks = get_all_stocks()
        analysis_data = []
        
        for stock in stocks:
            symbol = stock['symbol']
            
            # Get OHLCV data for the symbol (1 year)
            ohlcv_records = OHLCV.query.filter(
                OHLCV.symbol == symbol,
                OHLCV.timestamp >= start_datetime,
                OHLCV.timestamp <= end_datetime
            ).order_by(OHLCV.timestamp.asc()).all()
            
            if len(ohlcv_records) < 30:  # Need minimum 30 data points for basic indicators
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume
            } for r in ohlcv_records])
            
            if df.empty:
                continue
            
            # Filter out records where close = 0 (market closed)
            df = df[df['close'] > 0]
            
            if len(df) < 30:  # Re-check after filtering
                continue
            
            try:
                # Calculate indicators
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['ema_21'] = ta.ema(df['close'], length=21)
                df['ema_44'] = ta.ema(df['close'], length=44)
                df['ema_200'] = ta.ema(df['close'], length=200)
                
                # Calculate MACD
                macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
                if macd is not None and not macd.empty:
                    df['macd'] = macd[f'MACD_12_26_9']
                    df['macd_signal'] = macd[f'MACDs_12_26_9']
                    df['macd_hist'] = macd[f'MACDh_12_26_9']
                
                # Get latest values
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                
                # Determine MACD crossover
                macd_crossover = 'Neutral'
                if pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                    if pd.notna(prev['macd']) and pd.notna(prev['macd_signal']):
                        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
                            macd_crossover = 'Bullish'
                        elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
                            macd_crossover = 'Bearish'
                        elif latest['macd'] > latest['macd_signal']:
                            macd_crossover = 'Bullish'
                        elif latest['macd'] < latest['macd_signal']:
                            macd_crossover = 'Bearish'
                
                # Determine EMA crossovers (price crosses above EMA)
                ema_21_crossover = 'No'
                ema_44_crossover = 'No'
                ema_200_crossover = 'No'
                
                if pd.notna(latest['ema_21']) and pd.notna(prev['ema_21']):
                    if latest['close'] > latest['ema_21'] and prev['close'] <= prev['ema_21']:
                        ema_21_crossover = 'Yes'
                    elif latest['close'] > latest['ema_21']:
                        ema_21_crossover = 'Above'
                
                if pd.notna(latest['ema_44']) and pd.notna(prev['ema_44']):
                    if latest['close'] > latest['ema_44'] and prev['close'] <= prev['ema_44']:
                        ema_44_crossover = 'Yes'
                    elif latest['close'] > latest['ema_44']:
                        ema_44_crossover = 'Above'
                
                if pd.notna(latest['ema_200']) and pd.notna(prev['ema_200']):
                    if latest['close'] > latest['ema_200'] and prev['close'] <= prev['ema_200']:
                        ema_200_crossover = 'Yes'
                    elif latest['close'] > latest['ema_200']:
                        ema_200_crossover = 'Above'
                
                analysis_data.append({
                    'symbol': symbol,
                    'name': stock['name'],
                    'sector': stock.get('sector', 'N/A'),
                    'rsi': round(float(latest['rsi']), 2) if pd.notna(latest['rsi']) else None,
                    'macd_signal': macd_crossover,  # Changed from macd_crossover
                    'ema_crossover_21_44': ema_21_crossover if ema_21_crossover == 'Yes' else ('Above' if ema_44_crossover == 'Above' or ema_21_crossover == 'Above' else 'No'),  # Combined 21 and 44
                    'price_above_ema_200': ema_200_crossover,  # Changed from ema_200_crossover
                    'current_price': float(latest['close'])
                })
                
            except Exception as e:
                logger.error(f"Error calculating indicators for {symbol}: {str(e)}")
                continue
        
        logger.info(f"Analysis completed: {len(analysis_data)} stocks processed out of {len(stocks)} total stocks")
        
        return jsonify({
            'analysis_data': analysis_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_stocks': len(analysis_data),
            'total_in_universe': len(stocks)
        })
        
    except Exception as e:
        logger.error(f"Error in get_analysis_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/api/analysis/chart/<symbol>', methods=['GET'])
def get_chart_data(symbol):
    """Get detailed chart data with indicators for a specific stock (all available data)"""
    try:
        import pandas_ta as ta
        
        # Get all OHLCV data for the symbol
        ohlcv_records = OHLCV.query.filter(
            OHLCV.symbol == symbol
        ).order_by(OHLCV.timestamp.asc()).all()
        
        if not ohlcv_records:
            return jsonify({'error': 'No data found for this symbol'}), 404
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume
        } for r in ohlcv_records])
        
        # Set timestamp as index for resampling
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resample to daily intervals (1D)
        df_daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Reset index to get timestamp as column
        df_daily.reset_index(inplace=True)
        
        # Filter out records where close = 0 (market closed)
        df_daily = df_daily[df_daily['close'] > 0]
        
        if len(df_daily) < 30:  # Need minimum data points
            return jsonify({'error': 'Insufficient data for analysis'}), 404
        
        # Calculate indicators on daily data
        df_daily['rsi'] = ta.rsi(df_daily['close'], length=14)
        df_daily['ema_21'] = ta.ema(df_daily['close'], length=21)
        df_daily['ema_44'] = ta.ema(df_daily['close'], length=44)
        df_daily['ema_200'] = ta.ema(df_daily['close'], length=200)
        
        # Calculate MACD
        macd = ta.macd(df_daily['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df_daily['macd'] = macd[f'MACD_12_26_9']
            df_daily['macd_signal'] = macd[f'MACDs_12_26_9']
            df_daily['macd_hist'] = macd[f'MACDh_12_26_9']
        
        # Convert to JSON-serializable format
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
        
        # Get stock info
        stock_info = get_stock_by_symbol(symbol)
        
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
