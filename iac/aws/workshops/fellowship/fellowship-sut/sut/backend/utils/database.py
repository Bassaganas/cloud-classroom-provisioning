"""Database initialization and management."""
from flask import Flask
from models.user import db
import os

def init_db(app: Flask) -> None:
    """Initialize database with all models."""
    # Initialize db with app
    db.init_app(app)
    
    with app.app_context():
        # Import all models to register them
        from models.user import User
        from models.quest import Quest
        from models.member import Member
        from models.location import Location
        
        # Create all tables
        db.create_all()
        print("Database tables created successfully")
