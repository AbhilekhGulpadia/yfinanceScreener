from flask import Flask
from config import Config
from extensions import db, socketio, cors
from services.scheduler import init_scheduler
from routes.stocks import stocks_bp
from routes.portfolios import portfolios_bp
from routes.transactions import transactions_bp
from routes.watchlist import watchlist_bp
from routes.ohlcv import ohlcv_bp
from routes.main import main_bp
from routes.nifty500 import nifty500_bp
from routes.database import database_bp
from routes.analysis import analysis_bp
from routes.kite_auth import kite_auth_bp
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = 'your-secret-key'
    
    # Initialize extensions
    cors.init_app(app, resources={r"/*": {"origins": "*"}})
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(portfolios_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(ohlcv_bp)
    app.register_blueprint(nifty500_bp)
    app.register_blueprint(database_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(kite_auth_bp)
    
    # Create tables
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
        
    # Initialize scheduler
    init_scheduler(app)
    
    return app

app = create_app()

if __name__ == '__main__':
    # Run with HTTP
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
