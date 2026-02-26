"""Quest routes."""
from flask import Blueprint, request, jsonify, session
from flask_restx import Api, Resource, fields
from models.quest import Quest, db
from models.user import User
from datetime import datetime
from typing import Dict, Any, List, Optional

quests_bp = Blueprint('quests', __name__, url_prefix='/api')
quests_api = Api(quests_bp, doc=False, prefix='/quests')

# Request/Response models for Swagger
quest_model = quests_api.model('Quest', {
    'title': fields.String(required=True, description='Quest title'),
    'description': fields.String(description='Quest description'),
    'status': fields.String(description='Quest status (not_yet_begun, the_road_goes_ever_on, it_is_done, the_shadow_falls)'),
    'quest_type': fields.String(description='Quest type (The Journey, The Battle, The Fellowship, The Ring, Dark Magic)'),
    'priority': fields.String(description='Quest priority (Critical, Important, Standard)'),
    'is_dark_magic': fields.Boolean(description='Dark magic flag'),
    'assigned_to': fields.Integer(description='User ID of assignee'),
    'location_id': fields.Integer(description='Location ID'),
    'character_quote': fields.String(description='Character quote for completion')
})

quest_response_model = quests_api.model('QuestResponse', {
    'id': fields.Integer(description='Quest ID'),
    'title': fields.String(description='Quest title'),
    'description': fields.String(description='Quest description'),
    'status': fields.String(description='Quest status'),
    'quest_type': fields.String(description='Quest type'),
    'priority': fields.String(description='Quest priority'),
    'is_dark_magic': fields.Boolean(description='Dark magic flag'),
    'assigned_to': fields.Integer(description='User ID of assignee'),
    'location_id': fields.Integer(description='Location ID'),
    'location_name': fields.String(description='Location name'),
    'assignee_name': fields.String(description='Assignee username'),
    'character_quote': fields.String(description='Character quote'),
    'created_at': fields.String(description='Creation timestamp'),
    'updated_at': fields.String(description='Update timestamp'),
    'completed_at': fields.String(description='Completion timestamp')
})

def require_auth() -> bool:
    """Check if user is authenticated."""
    return session.get('user_id') is not None

@quests_api.route('/')
class QuestList(Resource):
    """Quest list endpoints."""
    
    @quests_api.marshal_list_with(quest_response_model)
    @quests_api.doc(description='Get all quests with optional filtering')
    def get(self) -> tuple[List[Dict[str, Any]], int]:
        """Get all quests with optional filtering."""
        query = Quest.query
        
        # Filter by status
        status = request.args.get('status')
        if status:
            # Map old status values for backward compatibility
            status_mapping = {
                'pending': 'not_yet_begun',
                'in_progress': 'the_road_goes_ever_on',
                'completed': 'it_is_done',
                'blocked': 'the_shadow_falls'
            }
            mapped_status = status_mapping.get(status, status)
            query = query.filter(Quest.status == mapped_status)
        
        # Filter by quest type
        quest_type = request.args.get('quest_type')
        if quest_type:
            query = query.filter(Quest.quest_type == quest_type)
        
        # Filter by priority
        priority = request.args.get('priority')
        if priority:
            query = query.filter(Quest.priority == priority)
        
        # Filter by dark magic
        dark_magic = request.args.get('dark_magic')
        if dark_magic is not None:
            is_dark_magic = dark_magic.lower() == 'true'
            query = query.filter(Quest.is_dark_magic == is_dark_magic)
        
        # Filter by location
        location_id = request.args.get('location_id')
        if location_id:
            query = query.filter(Quest.location_id == int(location_id))
        
        # Filter by assigned user
        assigned_to = request.args.get('assigned_to')
        if assigned_to:
            query = query.filter(Quest.assigned_to == int(assigned_to))
        
        quests = query.all()
        return [quest.to_dict() for quest in quests], 200
    
    @quests_api.expect(quest_model)
    @quests_api.marshal_with(quest_response_model)
    @quests_api.doc(description='Create a new quest', security='session')
    def post(self) -> tuple[Dict[str, Any], int]:
        """Create a new quest."""
        if not require_auth():
            return {'error': 'Authentication required'}, 401
        
        data = request.get_json()
        
        # Map old status values for backward compatibility
        status = data.get('status', 'not_yet_begun')
        status_mapping = {
            'pending': 'not_yet_begun',
            'in_progress': 'the_road_goes_ever_on',
            'completed': 'it_is_done',
            'blocked': 'the_shadow_falls'
        }
        mapped_status = status_mapping.get(status, status)
        
        quest = Quest(
            title=data.get('title'),
            description=data.get('description'),
            status=mapped_status,
            quest_type=data.get('quest_type'),
            priority=data.get('priority'),
            is_dark_magic=data.get('is_dark_magic', False),
            character_quote=data.get('character_quote'),
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
        
        # Map old status values for backward compatibility
        if 'status' in data:
            status = data.get('status')
            status_mapping = {
                'pending': 'not_yet_begun',
                'in_progress': 'the_road_goes_ever_on',
                'completed': 'it_is_done',
                'blocked': 'the_shadow_falls'
            }
            quest.status = status_mapping.get(status, status)
        
        quest.quest_type = data.get('quest_type', quest.quest_type)
        quest.priority = data.get('priority', quest.priority)
        quest.is_dark_magic = data.get('is_dark_magic', quest.is_dark_magic)
        quest.character_quote = data.get('character_quote', quest.character_quote)
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

@quests_api.route('/<int:quest_id>/complete')
class QuestComplete(Resource):
    """Quest completion endpoint."""
    
    @quests_api.marshal_with(quest_response_model)
    @quests_api.doc(description='Mark quest as complete', security='session')
    def put(self, quest_id: int) -> tuple[Dict[str, Any], int]:
        """Mark quest as complete."""
        if not require_auth():
            return {'error': 'Authentication required'}, 401
        
        quest = Quest.query.get_or_404(quest_id)
        
        # Set status to completed
        quest.status = 'it_is_done'
        quest.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Return quest with completion message
        result = quest.to_dict()
        result['message'] = 'The Quest Is Done!'
        
        return result, 200
