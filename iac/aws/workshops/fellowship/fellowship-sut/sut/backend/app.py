"""Main Flask application for the Fellowship Quest Tracker."""
from dotenv import load_dotenv
import os

# Load environment variables from .env file (if present)
# This must happen before any config is loaded
load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restx import Api
from config import config
from models.user import db
from utils.database import init_db
from utils.seed_data import seed_database
from routes.auth import auth_bp, auth_api
from routes.quests import quests_bp, quests_api
from routes.members import members_bp, members_api
from routes.locations import locations_bp, locations_api
from routes.npc_chat import npc_chat_bp, npc_chat_api
from routes.shop import shop_bp, shop_api

def create_app(config_name: str = None) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Configure session
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cross-site cookies for development
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    
    # Initialize CORS with specific origins (required when using credentials)
    # Allow both localhost:3000 (dev) and localhost (production via nginx)
    # Flask-CORS handles preflight OPTIONS requests automatically
    CORS(
        app,
        supports_credentials=True,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:3000",
                    "http://localhost",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1",
                ]
            }
        },
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )
    
    # Initialize database (this also initializes db)
    init_db(app)
    
    # Seed database with initial data
    seed_database(app)
    
    # Create main API with Swagger documentation
    api = Api(
        app,
        version='1.0',
        title='The Fellowship\'s Quest List API',
        description='REST API for tracking the Fellowship\'s epic journey through Middle-earth',
        doc='/api/swagger/',
        prefix='/api'
    )
    
    # Register blueprints (this registers both the blueprints and their Flask-RESTX routes)
    # Flask-RESTX Api objects bound to blueprints automatically register routes when blueprint is registered
    app.register_blueprint(auth_bp)
    app.register_blueprint(quests_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(npc_chat_bp)
    app.register_blueprint(shop_bp)
    
    # Note: We don't add the Api objects as namespaces because they're already bound to blueprints
    # Adding them as namespaces would cause route conflicts. The routes work from blueprints alone.
    # For Swagger, each Api has its own documentation, but we can add them to the main API if needed.
    # However, this requires creating Namespace objects, not using the Api objects directly.
    
    # Health check endpoint
    @app.route('/api/health')
    def health():
        """Health check endpoint."""
        return jsonify({'status': 'healthy', 'service': 'fellowship-quest-tracker'}), 200
    
    # API info endpoint (instead of root, since nginx handles root routing)
    @app.route('/api')
    def api_info():
        """API information endpoint."""
        return jsonify({
            'message': 'Welcome to The Fellowship\'s Quest List API',
            'version': '1.0',
            'docs': '/api/swagger/',
            'health': '/api/health'
        }), 200
    
    # Debug endpoint to list all registered routes (development only)
    if app.config.get('DEBUG'):
        @app.route('/api/routes')
        def list_routes():
            """List all registered routes (debug endpoint)."""
            routes = []
            for rule in app.url_map.iter_rules():
                if rule.rule.startswith('/api'):
                    routes.append({
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                        'path': str(rule)
                    })
            return jsonify({'routes': sorted(routes, key=lambda x: x['path'])}), 200
    
    return app

if __name__ == '__main__':
    try:
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        import traceback
        print(f"Error starting application: {e}")
        traceback.print_exc()
        raise