from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from .data_fetcher import fetch_ohlcv_data
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def run_job(app, job_func):
    """Wrapper to run job in app context"""
    with app.app_context():
        job_func()

def init_scheduler(app):
    """Initialize APScheduler with the Flask app context"""
    scheduler = BackgroundScheduler()
    
    # No automatic jobs - data is downloaded only on manual trigger
    logger.info("Scheduler initialized (manual trigger only)")
    
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    import atexit
    atexit.register(lambda: scheduler.shutdown())
