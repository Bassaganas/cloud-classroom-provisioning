"""Quest routes."""
from flask import Blueprint, request, jsonify, session
from flask_restx import Api, Resource, fields
from models.quest import Quest, db
from models.user import User
from typing import Dict, Any, List

quests_bp = Blueprint('quests', __name__, url_prefix='/api')
quests_api = Api(quests_bp, doc=False, prefix='/quests')

# Request/Response models for Swagger
quest_model = quests_api.model('Quest', {
    'title': fields.String(required=True, description='Quest title'),
    'description': fields.String(description='Quest description'),
    'status': fields.String(description='Quest status (pending, in_progress, completed)'),
    'assigned_to': fields.Integer(description='User ID of assignee'),
    'location_id': fields.Integer(description='Location ID')
})

quest_response_model = quests_api.model('QuestResponse', {
    'id': fields.Integer(description='Quest ID'),
    'title': fields.String(description='Quest title'),
    'description': fields.String(description='Quest description'),
    'status': fields.String(description='Quest status'),
    'assigned_to': fields.Integer(description='User ID of assignee'),
    'location_id': fields.Integer(description='Location ID'),
    'location_name': fields.String(description='Location name'),
    'assignee_name': fields.String(description='Assignee username'),
    'created_at': fields.String(description='Creation timestamp'),
    'updated_at': fields.String(description='Update timestamp')
})

def require_auth() -> bool:
    """Check if user is authenticated."""
    return session.get('user_id') is not None

@quests_api.route('/')
class QuestList(Resource):
    """Quest list endpoints."""
    
    @quests_api.marshal_list_with(quest_response_model)
    @quests_api.doc(description='Get all quests')
    def get(self) -> tuple[List[Dict[str, Any]], int]:
        """Get all quests."""
        quests = Quest.query.all()
        return [quest.to_dict() for quest in quests], 200
    
    @quests_api.expect(quest_model)
    @quests_api.marshal_with(quest_response_model)
    @quests_api.doc(description='Create a new quest', security='session')
    def post(self) -> tuple[Dict[str, Any], int]:
        """Create a new quest."""
        if not require_auth():
            return {'error': 'Authentication required'}, 401
        
        data = request.get_json()
        quest = Quest(
            title=data.get('title'),
            description=data.get('description'),
            status=data.get('status', 'pending'),
            assigned_to=data.get('assigned_to'),
            location_id=data.get('location_id')
        )
        
        db.session.add(quest)
        db.session.commit()
        
        return quest.to_dict(), 201

@quests_api.route('/<int:quest_id>')
class QuestDetail(Resource):
    """Quest detail endpoints."""
    
    @quests_api.marshal_with(quest_response_model)
    @quests_api.doc(description='Get quest by ID')
    def get(self, quest_id: int) -> tuple[Dict[str, Any], int]:
        """Get quest by ID."""
        quest = Quest.query.get_or_404(quest_id)
        return quest.to_dict(), 200
    
    @quests_api.expect(quest_model)
    @quests_api.marshal_with(quest_response_model)
    @quests_api.doc(description='Update quest', security='session')
    def put(self, quest_id: int) -> tuple[Dict[str, Any], int]:
        """Update quest."""
        if not require_auth():
            return {'error': 'Authentication required'}, 401
        
        quest = Quest.query.get_or_404(quest_id)
        data = request.get_json()
        
        quest.title = data.get('title', quest.title)
        quest.description = data.get('description', quest.description)
        quest.status = data.get('status', quest.status)
        quest.assigned_to = data.get('assigned_to', quest.assigned_to)
        quest.location_id = data.get('location_id', quest.location_id)
        
        db.session.commit()
        return quest.to_dict(), 200
    
    @quests_api.doc(description='Delete quest', security='session')
    def delete(self, quest_id: int) -> tuple[Dict[str, Any], int]:
        """Delete quest."""
        if not require_auth():
            return {'error': 'Authentication required'}, 401
        
        quest = Quest.query.get_or_404(quest_id)
        db.session.delete(quest)
        db.session.commit()
        
        return {'message': 'Quest deleted successfully'}, 200
