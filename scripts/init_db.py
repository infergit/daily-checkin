# scripts/init_db.py
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, create_app
from app.models.models import User, CheckIn

def init_db():
    """Initialize the database with tables and optional demo data."""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Optionally add demo user
        if '--with-demo-data' in sys.argv:
            create_demo_data()

def create_demo_data():
    """Create demo data for testing purposes"""
    # Check if demo user already exists
    if User.query.filter_by(username='demo').first():
        print("Demo user already exists!")
        return
    
    # Create demo user
    demo_user = User(username='demo', email='demo@example.com')
    demo_user.set_password('password123')
    db.session.add(demo_user)
    db.session.commit()
    print("Demo user created successfully!")
    
    # You can add demo check-ins here if needed
    
if __name__ == '__main__':
    init_db()
