"""Quest model for tracking Fellowship quests."""
from models.user import db
from datetime import datetime
from typing import Dict, Any, Optional

class Quest(db.Model):
    """Quest model for tracking Fellowship quests."""
    __tablename__ = 'quests'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, in_progress, completed
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relationships
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='quests')
    location = db.relationship('Location', foreign_keys=[location_id], backref='quests')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quest to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'location_id': self.location_id,
            'location_name': self.location.name if self.location else None,
            'assignee_name': self.assignee.username if self.assignee else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return f'<Quest {self.title}>'
