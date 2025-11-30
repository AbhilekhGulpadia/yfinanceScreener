from extensions import db
from datetime import datetime, timezone

def get_utc_now():
    """Helper function to get current UTC time"""
    return datetime.now(timezone.utc)

class Stock(db.Model):
    """Stock information table"""
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sector = db.Column(db.String(50))
    current_price = db.Column(db.Float)
    market_cap = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='stock', lazy=True, cascade='all, delete-orphan')
    watchlists = db.relationship('WatchList', backref='stock', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'sector': self.sector,
            'current_price': self.current_price,
            'market_cap': self.market_cap,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

class Portfolio(db.Model):
    """User portfolio table"""
    __tablename__ = 'portfolios'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    total_value = db.Column(db.Float, default=0.0)
    cash_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='portfolio', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'total_value': self.total_value,
            'cash_balance': self.cash_balance,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Transaction(db.Model):
    """Stock transactions table"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'BUY' or 'SELL'
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=get_utc_now)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'stock_id': self.stock_id,
            'stock_symbol': self.stock.symbol if self.stock else None,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'price': self.price,
            'total_amount': self.total_amount,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'notes': self.notes
        }

class WatchList(db.Model):
    """User watchlist table"""
    __tablename__ = 'watchlists'
    
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    target_price = db.Column(db.Float)
    notes = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=get_utc_now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'stock_symbol': self.stock.symbol if self.stock else None,
            'stock_name': self.stock.name if self.stock else None,
            'current_price': self.stock.current_price if self.stock else None,
            'target_price': self.target_price,
            'notes': self.notes,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }

class OHLCV(db.Model):
    """OHLCV (Open, High, Low, Close, Volume) data table"""
    __tablename__ = 'ohlcv_data'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger, nullable=False)
    last_updated = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)
    
    # Create composite unique constraint to prevent duplicate entries
    __table_args__ = (
        db.UniqueConstraint('symbol', 'timestamp', name='unique_symbol_timestamp'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

class ShortlistedStock(db.Model):
    """Shortlisted stocks from Weinstein screening"""
    __tablename__ = 'shortlisted_stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100))
    sector = db.Column(db.String(50))
    shortlisted_at = db.Column(db.DateTime, default=get_utc_now)
    price_at_shortlist = db.Column(db.Float)
    score = db.Column(db.Integer)
    stage = db.Column(db.String(20))
    ma30 = db.Column(db.Float)
    rs = db.Column(db.Float)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'sector': self.sector,
            'shortlisted_at': self.shortlisted_at.isoformat() if self.shortlisted_at else None,
            'price_at_shortlist': self.price_at_shortlist,
            'score': self.score,
            'stage': self.stage,
            'ma30': self.ma30,
            'rs': self.rs,
            'notes': self.notes
        }

class Trade(db.Model):
    """Trade records with brokerage and tax calculations"""
    __tablename__ = 'trades'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    trade_type = db.Column(db.String(10), nullable=False)  # BUY/SELL
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    trade_date = db.Column(db.DateTime, default=get_utc_now, index=True)
    
    # Charges breakdown
    brokerage = db.Column(db.Float, default=0.0)
    stt = db.Column(db.Float, default=0.0)
    exchange_charges = db.Column(db.Float, default=0.0)
    gst = db.Column(db.Float, default=0.0)
    sebi_charges = db.Column(db.Float, default=0.0)
    stamp_duty = db.Column(db.Float, default=0.0)
    total_charges = db.Column(db.Float, default=0.0)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'trade_type': self.trade_type,
            'quantity': self.quantity,
            'price': self.price,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'brokerage': self.brokerage,
            'stt': self.stt,
            'exchange_charges': self.exchange_charges,
            'gst': self.gst,
            'sebi_charges': self.sebi_charges,
            'stamp_duty': self.stamp_duty,
            'total_charges': self.total_charges,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
