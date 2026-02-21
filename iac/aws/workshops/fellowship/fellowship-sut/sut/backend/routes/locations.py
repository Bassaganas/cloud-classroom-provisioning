"""Location routes."""
from flask import Blueprint
from flask_restx import Api, Resource, fields
from models.location import Location
from typing import Dict, Any, List

locations_bp = Blueprint('locations', __name__, url_prefix='/api')
locations_api = Api(locations_bp, doc=False, prefix='/locations')

# Response model for Swagger
location_response_model = locations_api.model('LocationResponse', {
    'id': fields.Integer(description='Location ID'),
    'name': fields.String(description='Location name'),
    'description': fields.String(description='Location description'),
    'region': fields.String(description='Region name'),
    'created_at': fields.String(description='Creation timestamp')
})

@locations_api.route('/')
class LocationList(Resource):
    """Location list endpoints."""
    
    @locations_api.marshal_list_with(location_response_model)
    @locations_api.doc(description='Get all Middle-earth locations')
    def get(self) -> tuple[List[Dict[str, Any]], int]:
        """Get all locations."""
        locations = Location.query.all()
        return [location.to_dict() for location in locations], 200

@locations_api.route('/<int:location_id>')
class LocationDetail(Resource):
    """Location detail endpoints."""
    
    @locations_api.marshal_with(location_response_model)
    @locations_api.doc(description='Get location by ID')
    def get(self, location_id: int) -> tuple[Dict[str, Any], int]:
        """Get location by ID."""
        location = Location.query.get_or_404(location_id)
        return location.to_dict(), 200
