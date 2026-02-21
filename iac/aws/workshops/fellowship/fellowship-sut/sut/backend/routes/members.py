"""Fellowship member routes."""
from flask import Blueprint
from flask_restx import Api, Resource, fields
from models.member import Member
from typing import Dict, Any, List

members_bp = Blueprint('members', __name__, url_prefix='/api')
members_api = Api(members_bp, doc=False, prefix='/members')

# Response model for Swagger
member_response_model = members_api.model('MemberResponse', {
    'id': fields.Integer(description='Member ID'),
    'name': fields.String(description='Member name'),
    'race': fields.String(description='Member race'),
    'role': fields.String(description='Member role'),
    'status': fields.String(description='Member status'),
    'description': fields.String(description='Member description'),
    'created_at': fields.String(description='Creation timestamp')
})

@members_api.route('/')
class MemberList(Resource):
    """Fellowship member list endpoints."""
    
    @members_api.marshal_list_with(member_response_model)
    @members_api.doc(description='Get all Fellowship members')
    def get(self) -> tuple[List[Dict[str, Any]], int]:
        """Get all Fellowship members."""
        members = Member.query.all()
        return [member.to_dict() for member in members], 200

@members_api.route('/<int:member_id>')
class MemberDetail(Resource):
    """Fellowship member detail endpoints."""
    
    @members_api.marshal_with(member_response_model)
    @members_api.doc(description='Get member by ID')
    def get(self, member_id: int) -> tuple[Dict[str, Any], int]:
        """Get member by ID."""
        member = Member.query.get_or_404(member_id)
        return member.to_dict(), 200
