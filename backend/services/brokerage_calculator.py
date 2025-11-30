"""
Brokerage and Tax Calculator for Zerodha NSE Equity Trading

Calculates all charges based on Zerodha's NSE equity intraday and delivery rates.
Rates as of 2024.
"""

def calculate_buy_charges(quantity, price):
    """
    Calculate all charges for a BUY trade on Zerodha NSE Equity
    
    Args:
        quantity: Number of shares
        price: Price per share
    
    Returns:
        dict with breakdown of all charges
    """
    turnover = quantity * price
    
    # Brokerage: ₹20 per trade or 0.03% (whichever is lower)
    brokerage = min(20, turnover * 0.0003)
    
    # STT: 0% on buy side (only on sell)
    stt = 0
    
    # Exchange charges: 0.00325% of turnover
    exchange_charges = turnover * 0.0000325
    
    # SEBI charges: ₹10 per crore
    sebi_charges = (turnover / 10000000) * 10
    
    # GST: 18% on (brokerage + exchange charges)
    gst = (brokerage + exchange_charges) * 0.18
    
    # Stamp duty: 0.015% on buy side (capped at ₹1500 per trade)
    stamp_duty = min(turnover * 0.00015, 1500)
    
    # Total charges
    total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
    
    return {
        'brokerage': round(brokerage, 2),
        'stt': round(stt, 2),
        'exchange_charges': round(exchange_charges, 2),
        'gst': round(gst, 2),
        'sebi_charges': round(sebi_charges, 2),
        'stamp_duty': round(stamp_duty, 2),
        'total_charges': round(total_charges, 2),
        'turnover': round(turnover, 2)
    }


def calculate_sell_charges(quantity, price):
    """
    Calculate all charges for a SELL trade on Zerodha NSE Equity
    
    Args:
        quantity: Number of shares
        price: Price per share
    
    Returns:
        dict with breakdown of all charges
    """
    turnover = quantity * price
    
    # Brokerage: ₹20 per trade or 0.03% (whichever is lower)
    brokerage = min(20, turnover * 0.0003)
    
    # STT: 0.1% on sell side
    stt = turnover * 0.001
    
    # Exchange charges: 0.00325% of turnover
    exchange_charges = turnover * 0.0000325
    
    # SEBI charges: ₹10 per crore
    sebi_charges = (turnover / 10000000) * 10
    
    # GST: 18% on (brokerage + exchange charges)
    gst = (brokerage + exchange_charges) * 0.18
    
    # Stamp duty: 0% on sell side (only on buy)
    stamp_duty = 0
    
    # Total charges
    total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
    
    return {
        'brokerage': round(brokerage, 2),
        'stt': round(stt, 2),
        'exchange_charges': round(exchange_charges, 2),
        'gst': round(gst, 2),
        'sebi_charges': round(sebi_charges, 2),
        'stamp_duty': round(stamp_duty, 2),
        'total_charges': round(total_charges, 2),
        'turnover': round(turnover, 2)
    }


def calculate_trade_charges(trade_type, quantity, price):
    """
    Calculate charges based on trade type
    
    Args:
        trade_type: 'BUY' or 'SELL'
        quantity: Number of shares
        price: Price per share
    
    Returns:
        dict with breakdown of all charges
    """
    if trade_type.upper() == 'BUY':
        return calculate_buy_charges(quantity, price)
    elif trade_type.upper() == 'SELL':
        return calculate_sell_charges(quantity, price)
    else:
        raise ValueError(f"Invalid trade_type: {trade_type}. Must be 'BUY' or 'SELL'")


def calculate_total_cost(trade_type, quantity, price, charges):
    """
    Calculate total cost/proceeds including charges
    
    Args:
        trade_type: 'BUY' or 'SELL'
        quantity: Number of shares
        price: Price per share
        charges: dict from calculate_trade_charges
    
    Returns:
        float: total amount (positive for buy, negative for sell proceeds)
    """
    turnover = quantity * price
    
    if trade_type.upper() == 'BUY':
        # For buy: total cost = turnover + charges
        return round(turnover + charges['total_charges'], 2)
    elif trade_type.upper() == 'SELL':
        # For sell: net proceeds = turnover - charges
        return round(turnover - charges['total_charges'], 2)
    else:
        raise ValueError(f"Invalid trade_type: {trade_type}")
