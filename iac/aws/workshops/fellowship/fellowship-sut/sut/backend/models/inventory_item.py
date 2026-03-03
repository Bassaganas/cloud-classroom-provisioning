"""Purchased inventory item model."""
from models.user import db
from typing import Dict, Any


class InventoryItem(db.Model):
    """User-owned purchased item entry."""

    __tablename__ = 'inventory_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, unique=True)
    paid_price = db.Column(db.Integer, nullable=False)
    base_price_revealed = db.Column(db.Integer, nullable=False)
    savings_percent = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('User', foreign_keys=[user_id], backref='inventory_items')
    item = db.relationship('Item', foreign_keys=[item_id], backref='inventory_entry')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize full inventory item details."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_id': self.item_id,
            'item_name': self.item.name if self.item else None,
            'owner_character': self.item.owner_character if self.item else None,
            'description': self.item.description if self.item else None,
            'paid_price': self.paid_price,
            'base_price_revealed': self.base_price_revealed,
            'savings_percent': self.savings_percent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<InventoryItem user={self.user_id} item={self.item_id}>'
