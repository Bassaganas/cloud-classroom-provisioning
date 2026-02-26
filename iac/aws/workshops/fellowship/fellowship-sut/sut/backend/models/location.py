"""Location model for Middle-earth locations."""
from models.user import db
from typing import Dict, Any

class Location(db.Model):
    """Location model for Middle-earth locations."""
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    region = db.Column(db.String(100), nullable=False)  # Eriador, Rhovanion, Mordor, etc.
    map_x = db.Column(db.Float, nullable=True)  # X coordinate on map (pixel, 0-5000, horizontal)
    map_y = db.Column(db.Float, nullable=True)  # Y coordinate on map (pixel, 0-4344, vertical)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert location to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'region': self.region,
            'map_x': self.map_x,
            'map_y': self.map_y,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f'<Location {self.name}>'
