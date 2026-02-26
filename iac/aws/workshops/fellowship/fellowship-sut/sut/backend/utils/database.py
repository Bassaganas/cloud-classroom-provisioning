"""Database initialization and management."""
from flask import Flask
from models.user import db
from sqlalchemy import text
import os

def init_db(app: Flask) -> None:
    """Initialize database with all models and handle migrations."""
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
        
        # Handle migrations for existing quests table
        try:
            # Check if quests table exists and has old columns
            result = db.session.execute(text("PRAGMA table_info(quests)"))
            columns = {row[1]: row[2] for row in result}
            
            # Add new columns if they don't exist
            if 'quest_type' not in columns:
                db.session.execute(text("ALTER TABLE quests ADD COLUMN quest_type VARCHAR(50)"))
                print("Added quest_type column")
            
            if 'priority' not in columns:
                db.session.execute(text("ALTER TABLE quests ADD COLUMN priority VARCHAR(20)"))
                print("Added priority column")
            
            if 'is_dark_magic' not in columns:
                db.session.execute(text("ALTER TABLE quests ADD COLUMN is_dark_magic BOOLEAN DEFAULT 0"))
                print("Added is_dark_magic column")
            
            if 'character_quote' not in columns:
                db.session.execute(text("ALTER TABLE quests ADD COLUMN character_quote TEXT"))
                print("Added character_quote column")
            
            if 'completed_at' not in columns:
                db.session.execute(text("ALTER TABLE quests ADD COLUMN completed_at DATETIME"))
                print("Added completed_at column")
            
            # Migrate status values from old to new LOTR terminology
            status_mapping = {
                'pending': 'not_yet_begun',
                'in_progress': 'the_road_goes_ever_on',
                'completed': 'it_is_done',
                'blocked': 'the_shadow_falls'
            }
            
            for old_status, new_status in status_mapping.items():
                db.session.execute(
                    text("UPDATE quests SET status = :new_status WHERE status = :old_status"),
                    {'new_status': new_status, 'old_status': old_status}
                )
            
            # Update default status for new quests
            db.session.execute(text("UPDATE quests SET status = 'not_yet_begun' WHERE status = 'pending'"))
            
            db.session.commit()
            print("Database migration completed successfully")
        except Exception as e:
            # If migration fails, rollback and continue (table might be new)
            db.session.rollback()
            print(f"Migration note: {e} (this is normal for new databases)")
        
        # Handle migrations for existing locations table
        try:
            # Check if locations table exists
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"))
            table_exists = result.fetchone() is not None
            
            if table_exists:
                # Get existing columns
                result = db.session.execute(text("PRAGMA table_info(locations)"))
                columns = [row[1] for row in result]  # row[1] is the column name
                
                # Add new columns if they don't exist
                if 'map_x' not in columns:
                    db.session.execute(text("ALTER TABLE locations ADD COLUMN map_x REAL"))
                    print("Added map_x column to locations")
                
                if 'map_y' not in columns:
                    db.session.execute(text("ALTER TABLE locations ADD COLUMN map_y REAL"))
                    print("Added map_y column to locations")
                
                db.session.commit()
                print("Locations table migration completed successfully")
        except Exception as e:
            # If migration fails, rollback and continue
            db.session.rollback()
            print(f"Locations migration error: {e}")
            import traceback
            traceback.print_exc()