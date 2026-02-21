"""Authentication service."""
from models.user import User, db
from typing import Optional, Dict, Any

def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password."""
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None

def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID."""
    return User.query.get(user_id)

def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username."""
    return User.query.filter_by(username=username).first()
