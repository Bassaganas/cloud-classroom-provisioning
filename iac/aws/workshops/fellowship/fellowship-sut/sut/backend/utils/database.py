"""Database initialization and management."""
from flask import Flask
from models.user import db
from sqlalchemy import text
import os

def init_db(app: Flask) -> None:
    # Initialize db with app
    db.init_app(app)

    with app.app_context():
        # Handle migrations for existing inventory_items table
        try:
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_items'"))
            table_exists = result.fetchone() is not None

            if table_exists:
                result = db.session.execute(text("PRAGMA table_info(inventory_items)"))
                columns = [row[1] for row in result]

                if 'paid_price' not in columns:
                    db.session.execute(text("ALTER TABLE inventory_items ADD COLUMN paid_price INTEGER DEFAULT 0"))
                    print("Added paid_price column to inventory_items")

                if 'base_price_revealed' not in columns:
                    db.session.execute(text("ALTER TABLE inventory_items ADD COLUMN base_price_revealed INTEGER DEFAULT 0"))
                    print("Added base_price_revealed column to inventory_items")

                if 'savings_percent' not in columns:
                    db.session.execute(text("ALTER TABLE inventory_items ADD COLUMN savings_percent FLOAT DEFAULT 0"))
                    print("Added savings_percent column to inventory_items")

                if 'created_at' not in columns:
                    db.session.execute(text("ALTER TABLE inventory_items ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                    print("Added created_at column to inventory_items")

                # Fix for legacy acquired_price column: add if missing, make nullable if present
                if 'acquired_price' not in columns:
                    db.session.execute(text("ALTER TABLE inventory_items ADD COLUMN acquired_price INTEGER NULL"))
                    print("Added acquired_price column to inventory_items (nullable)")
                else:
                    # Try to make it nullable if not already
                    try:
                        db.session.execute(text("ALTER TABLE inventory_items ALTER COLUMN acquired_price DROP NOT NULL"))
                        print("Made acquired_price column nullable")
                    except Exception as e:
                        print(f"Could not alter acquired_price nullability: {e}")

                db.session.commit()
                print("Inventory items table migration completed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Inventory items migration note: {e} (this is normal for new databases)")
        # Import all models to register them
        from models.user import User
        from models.quest import Quest
        from models.member import Member
        from models.location import Location
        from models.item import Item
        from models.inventory_item import InventoryItem
        
        # Create all tables
        db.create_all()
        print("Database tables created successfully")
        
        # Handle migrations for existing users table
        try:
            users_result = db.session.execute(text("PRAGMA table_info(users)"))
            user_columns = {row[1]: row[2] for row in users_result}

            if 'gold' not in user_columns:
                db.session.execute(text("ALTER TABLE users ADD COLUMN gold INTEGER DEFAULT 500"))
                print("Added gold column to users")

            db.session.execute(text("UPDATE users SET gold = 500 WHERE gold IS NULL"))
            db.session.commit()
            print("Users table migration completed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Users migration note: {e} (this is normal for new databases)")

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

        # Handle migrations for existing items table
        try:
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='items'"))
            table_exists = result.fetchone() is not None

            if table_exists:
                result = db.session.execute(text("PRAGMA table_info(items)"))
                columns = [row[1] for row in result]

                if 'owner_character' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN owner_character VARCHAR(80) DEFAULT 'gandalf'"))
                    print("Added owner_character column to items")

                if 'personality_profile' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN personality_profile VARCHAR(40) DEFAULT 'bargainer'"))
                    print("Added personality_profile column to items")

                if 'asking_price' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN asking_price INTEGER DEFAULT 100"))
                    print("Added asking_price column to items")

                if 'is_sold' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN is_sold BOOLEAN DEFAULT 0"))
                    print("Added is_sold column to items")

                if 'created_at' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN created_at DATETIME"))
                    print("Added created_at column to items")

                if 'updated_at' not in columns:
                    db.session.execute(text("ALTER TABLE items ADD COLUMN updated_at DATETIME"))
                    print("Added updated_at column to items")

                db.session.execute(text("UPDATE items SET asking_price = COALESCE(asking_price, base_price, 100)"))
                db.session.execute(text("UPDATE items SET personality_profile = COALESCE(personality_profile, 'bargainer')"))
                db.session.execute(text("UPDATE items SET owner_character = COALESCE(owner_character, 'gandalf')"))
                db.session.execute(text("UPDATE items SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
                db.session.execute(text("UPDATE items SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
                db.session.commit()
                print("Items table migration completed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Items migration note: {e} (this is normal for new databases)")