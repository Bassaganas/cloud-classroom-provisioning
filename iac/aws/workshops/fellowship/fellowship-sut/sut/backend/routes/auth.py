"""Authentication routes."""
from flask import Blueprint, request, jsonify, session
from flask_restx import Api, Resource, fields
from models.user import User, db
from services.auth_service import authenticate_user
from typing import Dict, Any

auth_bp = Blueprint('auth', __name__, url_prefix='/api')
auth_api = Api(auth_bp, doc=False, prefix='/auth')

# Request/Response models for Swagger
login_model = auth_api.model('Login', {
    'username': fields.String(required=True, description='Username'),
    'password': fields.String(required=True, description='Password')
})

user_response_model = auth_api.model('UserResponse', {
    'id': fields.Integer(description='User ID'),
    'username': fields.String(description='Username'),
    'email': fields.String(description='Email'),
    'role': fields.String(description='Fellowship member role'),
    'gold': fields.Integer(description='Current gold balance'),
})

login_response_model = auth_api.model('LoginResponse', {
    'message': fields.String(description='Success message'),
    'user': fields.Nested(user_response_model, description='User information')
})

@auth_api.route('/login')
class Login(Resource):
    """User login endpoint."""
    
    @auth_api.expect(login_model)
    @auth_api.marshal_with(login_response_model)
    @auth_api.doc(description='Authenticate user and create session')
    def post(self) -> tuple[Dict[str, Any], int]:
        """Login user."""
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return {'error': 'Username and password are required'}, 400
        
        user = authenticate_user(username, password)
        if not user:
            return {'error': 'Invalid credentials'}, 401
        
        # Create session
        session['user_id'] = user.id
        session['username'] = user.username
        
        return {
            'message': 'Login successful',
            'user': user.to_dict()
        }, 200

@auth_api.route('/logout')
class Logout(Resource):
    """User logout endpoint."""
    
    @auth_api.doc(description='Logout user and destroy session')
    def post(self) -> tuple[Dict[str, Any], int]:
        """Logout user."""
        session.clear()
        return {'message': 'Logout successful'}, 200

@auth_api.route('/me')
class CurrentUser(Resource):
    """Get current authenticated user."""
    
    @auth_api.marshal_with(user_response_model)
    @auth_api.doc(description='Get current authenticated user information')
    def get(self) -> tuple[Dict[str, Any], int]:
        """Get current user."""
        user_id = session.get('user_id')
        if not user_id:
            return {'error': 'Not authenticated'}, 401
        
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        return user.to_dict(), 200
