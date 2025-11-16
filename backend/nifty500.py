"""
Nifty 500 Stock Symbols with complete information
Loads data from nifty500_data.json file
"""

import json
import os

# Get the directory of this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(CURRENT_DIR, 'nifty500_data.json')

# Load stock data from JSON file
def load_stock_data():
    """Load stock data from JSON file"""
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {JSON_FILE_PATH} not found. Using empty list.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return []

# Load data once when module is imported
NIFTY_500_STOCKS = load_stock_data()

def get_all_stocks():
    """Return list of all stock objects with complete information"""
    return NIFTY_500_STOCKS

def get_all_symbols():
    """Return list of all stock symbols (with .NS suffix)"""
    return [stock['symbol'] for stock in NIFTY_500_STOCKS]

def get_stock_by_symbol(symbol):
    """Get stock information by symbol"""
    # Handle both with and without .NS suffix
    if not symbol.endswith('.NS'):
        symbol = f"{symbol}.NS"
    
    for stock in NIFTY_500_STOCKS:
        if stock['symbol'] == symbol:
            return stock
    return None

def get_stocks_by_sector(sector):
    """Get all stocks in a specific sector"""
    return [stock for stock in NIFTY_500_STOCKS if stock['sector'].lower() == sector.lower()]

def get_nifty50_stocks():
    """Get all Nifty 50 stocks"""
    return [stock for stock in NIFTY_500_STOCKS if stock.get('nifty50', False)]

def get_nifty200_stocks():
    """Get all Nifty 200 stocks"""
    return [stock for stock in NIFTY_500_STOCKS if stock.get('nifty200', False)]

def get_nifty500_stocks():
    """Get all Nifty 500 stocks"""
    return [stock for stock in NIFTY_500_STOCKS if stock.get('nifty500', False)]

def get_all_sectors():
    """Get list of all unique sectors"""
    sectors = set(stock['sector'] for stock in NIFTY_500_STOCKS)
    return sorted(list(sectors))

def get_symbol_without_suffix(symbol):
    """Remove .NS suffix from symbol"""
    return symbol.replace('.NS', '')

def add_ns_suffix(symbol):
    """Add .NS suffix to symbol if not present"""
    if not symbol.endswith('.NS'):
        return f"{symbol}.NS"
    return symbol

def get_stock_count():
    """Get total count of stocks"""
    return len(NIFTY_500_STOCKS)

def search_stocks(query):
    """Search stocks by name or symbol"""
    query = query.lower()
    results = []
    for stock in NIFTY_500_STOCKS:
        if query in stock['name'].lower() or query in stock['symbol'].lower():
            results.append(stock)
    return results
