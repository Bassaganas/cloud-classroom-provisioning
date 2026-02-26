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
    status = db.Column(db.String(50), nullable=False, default='not_yet_begun')  # not_yet_begun, the_road_goes_ever_on, it_is_done, the_shadow_falls
    quest_type = db.Column(db.String(50), nullable=True)  # The Journey, The Battle, The Fellowship, The Ring, Dark Magic
    priority = db.Column(db.String(20), nullable=True)  # Critical, Important, Standard
    is_dark_magic = db.Column(db.Boolean, default=False, nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    character_quote = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='quests')
    location = db.relationship('Location', foreign_keys=[location_id], backref='quests')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quest to dictionary."""
        # Map old status values to new LOTR terminology for backward compatibility
        status_mapping = {
            'pending': 'not_yet_begun',
            'in_progress': 'the_road_goes_ever_on',
            'completed': 'it_is_done',
            'blocked': 'the_shadow_falls'
        }
        mapped_status = status_mapping.get(self.status, self.status)
        
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': mapped_status,
            'quest_type': self.quest_type,
            'priority': self.priority,
            'is_dark_magic': self.is_dark_magic,
            'assigned_to': self.assigned_to,
            'location_id': self.location_id,
            'location_name': self.location.name if self.location else None,
            'assignee_name': self.assignee.username if self.assignee else None,
            'character_quote': self.character_quote,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self) -> str:
        return f'<Quest {self.title}>'
