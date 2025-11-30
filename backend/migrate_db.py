"""
Database migration script to create new tables for Shortlist and Trading features
Run this script to create the shortlisted_stocks and trades tables
"""

from app import create_app
from extensions import db
from models import ShortlistedStock, Trade

def migrate_database():
    """Create new tables for shortlist and trading features"""
    app = create_app()
    
    with app.app_context():
        print("Creating new tables...")
        
        # Create tables
        db.create_all()
        
        print("✓ Tables created successfully!")
        print("  - shortlisted_stocks")
        print("  - trades")
        print("\nDatabase migration complete!")

if __name__ == '__main__':
    migrate_database()
