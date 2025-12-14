import os

class Config:
    """Database configuration"""
    
    # Get the base directory of the app
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # SQLite database file path with timeout parameter
    # Use /app/data for Docker volumes, fallback to BASE_DIR for local development
    DB_DIR = os.environ.get('DB_DIR', BASE_DIR)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URI',
        f'sqlite:///{os.path.join(DB_DIR, "stock_analyzer.db")}?timeout=30'
    )
    
    # Disable SQLAlchemy modification tracking (saves resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Kite Connect Credentials - Read from environment variables
    KITE_API_KEY = os.environ.get('KITE_API_KEY', 'iyi9a2huwplqqzvg')
    KITE_API_SECRET = os.environ.get('KITE_API_SECRET', 'zd5b9dc6shmnwxjuquydj0rgjalkp526')
    
    # Secret key for sessions (change in production)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # SQLAlchemy engine options for better concurrency
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Test connections before using them
        'pool_recycle': 300,    # Recycle connections after 5 minutes
        'connect_args': {
            'timeout': 30,       # Connection timeout in seconds
            'check_same_thread': False  # Allow SQLite access from multiple threads
        }
    }
