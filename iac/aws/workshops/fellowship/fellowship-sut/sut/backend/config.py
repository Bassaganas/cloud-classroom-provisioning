"""Configuration settings for the Fellowship Quest Tracker application."""
import os
from pathlib import Path

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # SQLite database configuration
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = Path('/app/data')
    # Ensure data directory exists
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create data directory: {e}")
    DATABASE_PATH = DATA_DIR / 'fellowship.db'
    # Use environment variable if set, otherwise use default path
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Use 4 slashes for absolute path: sqlite:////absolute/path
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Configuration
    RESTX_MASK_SWAGGER = False
    RESTX_VALIDATE = True
    RESTX_ERROR_404_HELP = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    FLASK_ENV = 'production'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
