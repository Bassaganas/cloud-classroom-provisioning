"""Market item model for NPC bargaining."""
from models.user import db
from typing import Dict, Any


class Item(db.Model):
    """Unique sellable item owned by an NPC character."""

    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_character = db.Column(db.String(80), nullable=False, index=True)
    personality_profile = db.Column(db.String(40), nullable=False, default='bargainer')
    base_price = db.Column(db.Integer, nullable=False)
    asking_price = db.Column(db.Integer, nullable=False)
    is_sold = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    def to_public_dict(self) -> Dict[str, Any]:
        """Serialize without revealing hidden base price."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_character': self.owner_character,
            'personality_profile': self.personality_profile,
            'asking_price': self.asking_price,
            'is_sold': self.is_sold,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f'<Item {self.name}>'
