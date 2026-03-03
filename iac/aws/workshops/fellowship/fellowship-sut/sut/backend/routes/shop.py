"""Shop routes for bargaining market gameplay."""
from typing import Any, Dict, Optional

from flask import Blueprint, request, session
from flask_restx import Api, Resource, fields

from models.user import User
from services.shop_service import ShopService


shop_bp = Blueprint('shop', __name__, url_prefix='/api')
shop_api = Api(shop_bp, doc=False, prefix='/shop')

purchase_model = shop_api.model('ShopPurchaseRequest', {
    'item_id': fields.Integer(required=True, description='Unique item ID'),
    'paid_price': fields.Integer(required=True, description='Agreed paid price'),
})


def _require_auth() -> bool:
    return session.get('user_id') is not None


def _get_current_user() -> Optional[User]:
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


@shop_api.route('/items')
class ShopItems(Resource):
    def get(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        character = (request.args.get('character') or '').strip().lower() or None
        items = ShopService.list_available_items(character=character)
        return {'items': items}, 200


@shop_api.route('/items/<int:item_id>')
class ShopItemDetail(Resource):
    def get(self, item_id: int) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        item = ShopService.get_item_public(item_id)
        if not item:
            return {'error': 'Item not found'}, 404
        return {'item': item}, 200


@shop_api.route('/purchase')
class ShopPurchase(Resource):
    @shop_api.expect(purchase_model)
    def post(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        payload = request.get_json() or {}
        item_id = payload.get('item_id')
        paid_price = payload.get('paid_price')

        if not item_id or paid_price is None:
            return {'error': 'item_id and paid_price are required'}, 400

        try:
            result = ShopService.purchase_item(user_id=user.id, item_id=int(item_id), paid_price=int(paid_price))
            return result, 200
        except ValueError as error:
            return {'error': str(error)}, 400


@shop_api.route('/inventory')
class ShopInventory(Resource):
    def get(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        inventory = ShopService.get_user_inventory(user.id)
        return {'inventory': inventory}, 200


@shop_api.route('/stats')
class ShopStats(Resource):
    def get(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        stats = ShopService.get_user_stats(user.id)
        return {'stats': stats}, 200


@shop_api.route('/balance')
class ShopBalance(Resource):
    def get(self) -> tuple[Dict[str, Any], int]:
        if not _require_auth():
            return {'error': 'Authentication required'}, 401

        user = _get_current_user()
        if not user:
            return {'error': 'User not found'}, 404

        return ShopService.get_balance(user.id), 200


@shop_api.route('/test-reset')
class TestReset(Resource):
    """Reset shop state for testing - marks all items as not sold and resets user gold."""
    def post(self) -> tuple[Dict[str, Any], int]:
        import os
        # Only allow in non-production environments
        if os.getenv('FLASK_ENV') in {'production', 'prod'}:
            return {'error': 'Test reset not allowed in production'}, 403
        
        try:
            ShopService.reset_for_tests()
            return {'success': True, 'message': 'Test state reset successfully'}, 200
        except Exception as e:
            return {'error': str(e)}, 500
