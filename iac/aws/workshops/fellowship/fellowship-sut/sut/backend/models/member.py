"""Fellowship member model."""
from models.user import db
from typing import Dict, Any

class Member(db.Model):
    """Fellowship member model."""
    __tablename__ = 'members'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    race = db.Column(db.String(50), nullable=False)  # Hobbit, Human, Elf, Dwarf, Wizard
    role = db.Column(db.String(100), nullable=False)  # Ring-bearer, Companion, Ranger, etc.
    status = db.Column(db.String(20), nullable=False, default='active')  # active, inactive
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert member to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'race': self.race,
            'role': self.role,
            'status': self.status,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f'<Member {self.name}>'
