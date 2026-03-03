"""Shop service for bargaining, purchases, balance, and personal stats."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.user import User, db
from models.item import Item
from models.inventory_item import InventoryItem


class ShopService:
    """Business logic for item listings and purchases."""

    @classmethod
    def list_available_items(cls, character: Optional[str] = None) -> List[Dict[str, Any]]:
        query = Item.query.filter(Item.is_sold.is_(False))
        if character:
            query = query.filter(Item.owner_character == character.lower())
        return [item.to_public_dict() for item in query.order_by(Item.id.asc()).all()]

    @classmethod
    def get_item_public(cls, item_id: int) -> Optional[Dict[str, Any]]:
        item = Item.query.get(item_id)
        if not item:
            return None
        return item.to_public_dict()

    @classmethod
    def get_balance(cls, user_id: int) -> Dict[str, Any]:
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        return {'gold': user.gold}

    @classmethod
    def purchase_item(cls, user_id: int, item_id: int, paid_price: int) -> Dict[str, Any]:
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')

        item = Item.query.get(item_id)
        if not item:
            raise ValueError('Item not found')

        if item.is_sold:
            raise ValueError('Item is already sold')

        if paid_price <= 0:
            raise ValueError('Paid price must be positive')

        if user.gold < paid_price:
            raise ValueError('Insufficient gold')

        savings_percent = ((item.base_price - paid_price) / item.base_price) * 100 if item.base_price else 0.0

        user.gold -= paid_price
        item.is_sold = True

        entry = InventoryItem(
            user_id=user.id,
            item_id=item.id,
            paid_price=paid_price,
            base_price_revealed=item.base_price,
            savings_percent=round(savings_percent, 2),
        )

        db.session.add(entry)
        db.session.commit()

        return {
            'purchase': entry.to_dict(),
            'balance': {'gold': user.gold},
            'deal_quality': 'good' if savings_percent > 0 else 'bad' if savings_percent < 0 else 'fair',
        }

    @classmethod
    def get_user_inventory(cls, user_id: int) -> List[Dict[str, Any]]:
        entries = (
            InventoryItem.query
            .filter(InventoryItem.user_id == user_id)
            .order_by(InventoryItem.created_at.desc())
            .all()
        )
        return [entry.to_dict() for entry in entries]

    @classmethod
    def get_user_stats(cls, user_id: int) -> Dict[str, Any]:
        entries = cls.get_user_inventory(user_id)
        if not entries:
            return {
                'purchased_count': 0,
                'best_bargain_percent': 0,
                'average_savings_percent': 0,
            }

        savings_values = [float(entry['savings_percent']) for entry in entries]
        average = sum(savings_values) / len(savings_values)

        return {
            'purchased_count': len(entries),
            'best_bargain_percent': round(max(savings_values), 2),
            'average_savings_percent': round(average, 2),
        }
