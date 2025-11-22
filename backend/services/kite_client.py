import logging
from kiteconnect import KiteConnect
from flask import current_app
import pandas as pd
from datetime import datetime, timedelta
import os
import json

logger = logging.getLogger(__name__)

class KiteClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KiteClient, cls).__new__(cls)
            cls._instance.kite = None
            cls._instance.instruments_map = {}
            cls._instance.access_token = None
        return cls._instance
    
    def initialize(self):
        """Initialize KiteConnect instance with API key from config"""
        if not self.kite:
            api_key = current_app.config.get('KITE_API_KEY')
            if not api_key:
                logger.error("Kite API Key not found in config")
                return
            
            self.kite = KiteConnect(api_key=api_key)
            logger.info("KiteConnect initialized")
            
            # Try to load access token from file if exists (simple persistence)
            self._load_token()

    def get_login_url(self):
        """Get the login URL for the user"""
        if not self.kite:
            self.initialize()
        return self.kite.login_url()

    def generate_session(self, request_token):
        """Generate session using request token"""
        if not self.kite:
            self.initialize()
            
        api_secret = current_app.config.get('KITE_API_SECRET')
        if not api_secret:
            raise ValueError("Kite API Secret not found in config")
            
        try:
            data = self.kite.generate_session(request_token, api_secret=api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self._save_token()
            
            # Fetch instruments after successful login
            self.fetch_instruments()
            
            return data
        except Exception as e:
            logger.error(f"Error generating session: {str(e)}")
            raise

    def _save_token(self):
        """Save access token to file"""
        try:
            with open('kite_token.json', 'w') as f:
                json.dump({'access_token': self.access_token}, f)
        except Exception as e:
            logger.error(f"Error saving token: {str(e)}")

    def _load_token(self):
        """Load access token from file"""
        try:
            if os.path.exists('kite_token.json'):
                with open('kite_token.json', 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('access_token')
                    if self.access_token:
                        self.kite.set_access_token(self.access_token)
                        logger.info("Loaded access token from file")
                        # Fetch instruments if we have a token
                        # Note: Token might be expired, handle that later
        except Exception as e:
            logger.error(f"Error loading token: {str(e)}")

    def fetch_instruments(self):
        """Fetch and cache instrument tokens"""
        if not self.kite or not self.access_token:
            logger.error("Cannot fetch instruments: not logged in")
            return False
            
        try:
            instruments = self.kite.instruments("NSE")
            self.instruments_map = {
                inst['tradingsymbol']: inst['instrument_token'] 
                for inst in instruments
            }
            logger.info(f"Fetched {len(self.instruments_map)} instruments from Kite")
            return True
        except Exception as e:
            logger.error(f"Error fetching instruments: {str(e)}")
            return False
    
    def get_instruments(self, exchange='NSE'):
        """Get all instruments for an exchange"""
        if not self.kite or not self.access_token:
            raise Exception("Kite client not initialized or not logged in")
        
        try:
            return self.kite.instruments(exchange)
        except Exception as e:
            logger.error(f"Error getting instruments for {exchange}: {str(e)}")
            raise

    def get_instrument_token(self, symbol):
        """Get instrument token for a symbol (e.g., RELIANCE)"""
        # Handle Yahoo format (RELIANCE.NS -> RELIANCE)
        clean_symbol = symbol.replace('.NS', '')
        
        if not self.instruments_map:
            self.fetch_instruments()
            
        return self.instruments_map.get(clean_symbol)

    def fetch_historical_data(self, symbol, from_date, to_date, interval='day'):
        """
        Fetch historical data
        interval: minute, day, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute
        """
        if not self.kite or not self.access_token:
            raise ValueError("Kite client not initialized or not logged in")
            
        token = self.get_instrument_token(symbol)
        if not token:
            raise ValueError(f"Instrument token not found for {symbol}")
            
        try:
            records = self.kite.historical_data(
                token, 
                from_date, 
                to_date, 
                interval
            )
            
            # Convert to DataFrame for consistency with existing logic
            df = pd.DataFrame(records)
            if not df.empty:
                # Rename columns to match existing schema if needed
                # Kite returns: date, open, high, low, close, volume
                df.rename(columns={'date': 'timestamp'}, inplace=True)
                
                # Ensure timestamp is timezone aware (Kite returns it with offset usually)
                # If not, localize it.
                
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            raise

kite_client = KiteClient()
