"""NPC chat routes backed by Azure AI service."""
import uuid
from typing import Any, Dict

from flask import Blueprint, request, session
from flask_restx import Api, Resource, fields

from models.user import User
from services.npc_chat_service import NpcChatService

npc_chat_bp = Blueprint('npc_chat', __name__, url_prefix='/api')
npc_chat_api = Api(npc_chat_bp, doc=False, prefix='/chat')

chat_start_model = npc_chat_api.model('ChatStartRequest', {
    'character': fields.String(required=False, description='frodo|sam|gandalf'),
})

chat_message_model = npc_chat_api.model('ChatMessageRequest', {
    'character': fields.String(required=False, description='frodo|sam|gandalf'),
    'message': fields.String(required=True, description='User message'),
})


def _require_auth() -> bool:
    return session.get('user_id') is not None


def _get_current_user() -> User:
    user_id = session.get('user_id')
    return User.query.get(user_id)


def _get_chat_scope_id() -> str:
    scope_id = session.get('chat_scope_id')
    if not scope_id:
        scope_id = uuid.uuid4().hex
        session['chat_scope_id'] = scope_id
    return scope_id


@npc_chat_api.route('/start')
class ChatStart(Resource):
    @npc_chat_api.expect(chat_start_model)
    def post(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        data = request.get_json() or {}
        scope_id = _get_chat_scope_id()
        payload = NpcChatService.start_conversation(
            user_id=user.id,
            username=user.username,
            character=data.get('character'),
            scope_id=scope_id,
        )
        return payload, 200


@npc_chat_api.route('/message')
class ChatMessage(Resource):
    @npc_chat_api.expect(chat_message_model)
    def post(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        if not message:
            return {'error': 'message is required'}, 400

        scope_id = _get_chat_scope_id()
        payload = NpcChatService.send_message(
            user_id=user.id,
            username=user.username,
            character=data.get('character'),
            user_message=message,
            scope_id=scope_id,
        )
        return payload, 200


@npc_chat_api.route('/session')
class ChatSession(Resource):
    def get(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        character = request.args.get('character')
        scope_id = _get_chat_scope_id()
        payload = NpcChatService.get_session(user_id=user.id, character=character, scope_id=scope_id)
        return payload, 200


@npc_chat_api.route('/reset')
class ChatReset(Resource):
    @npc_chat_api.expect(chat_start_model)
    def post(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        data = request.get_json() or {}
        scope_id = _get_chat_scope_id()
        payload = NpcChatService.reset_session(user_id=user.id, character=data.get('character'), scope_id=scope_id)
        return payload, 200
