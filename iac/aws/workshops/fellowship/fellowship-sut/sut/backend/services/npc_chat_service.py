"""Azure AI powered NPC chat service for realistic LOTR-style companions."""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from openai import AzureOpenAI

from models.location import Location
from models.quest import Quest
from services.shop_service import ShopService
from services.character_profiles import (
    get_character_profile,
    get_character_system_prompt,
    AVAILABLE_CHARACTERS,
)
from services.quest_generation_service import generate_quest, should_offer_quest

# Configure logging
logger = logging.getLogger(__name__)

NpcCharacter = str
ConversationTurn = Dict[str, str]


class NpcChatService:
    """Handles NPC conversation flow, goal nudging, and Azure AI completions."""

    _conversation_store: Dict[str, List[ConversationTurn]] = {}
    _negotiation_store: Dict[str, Dict[str, Any]] = {}

    _personality_defaults: Dict[str, Dict[str, float]] = {
        "stingy": {"patience": 2, "concession": 0.05, "boredom": 0.20, "accept_ratio": 1.0},
        "bargainer": {"patience": 4, "concession": 0.10, "boredom": 0.10, "accept_ratio": 0.95},
        "generous": {"patience": 5, "concession": 0.15, "boredom": 0.05, "accept_ratio": 0.90},
        "sentimental": {"patience": 6, "concession": 0.20, "boredom": 0.05, "accept_ratio": 0.92},
    }

    _opener_pool: Dict[NpcCharacter, List[str]] = {
        "frodo": [
            "Before we move, tell me this: what burden are you avoiding today?",
            "I have a feeling the smallest task might matter most today. Which one is it?",
            "If we could finish one thing before dusk, what should it be?",
        ],
        "sam": [
            "Right then, what can we get done first so the road gets easier?",
            "You look ready. Which quest should we push over the line now?",
            "If we tidy one trouble before second breakfast, which one would you pick?",
        ],
        "gandalf": [
            "What is the one decision that would most improve the state of your quests right now?",
            "Name the most urgent unfinished matter, and we shall act on it.",
            "Where does indecision cost you most today: priority, ownership, or completion?",
        ],
    }

    _fallback_replies: Dict[NpcCharacter, List[str]] = {
        "frodo": [
            "I hear you. Let us take one step that lightens the load now.",
            "Even a small act done now can spare us greater trouble later.",
        ],
        "sam": [
            "Aye, that makes sense. Let us pick one task and finish it proper.",
            "Good thinking. Start small, finish strong, then we move to the next.",
        ],
        "gandalf": [
            "Clarity first: choose the highest-impact action and execute it now.",
            "Do not wait for perfect conditions. Act on the essential next step.",
        ],
    }

    # Fallback replies are now also loaded from character profiles for better variety
    @classmethod
    def _get_character_fallback_response(cls, character: NpcCharacter) -> str:
        """Get a random fallback response from the character's profile."""
        profile = get_character_profile(character)
        responses = profile.get("fallback_responses", [])
        if responses:
            return random.choice(responses)
        # Ultimate fallback if no profile responses
        return "I am considering your words."

    _side_quest_titles: List[str] = [
        "Scout the Silent Pass",
        "Secure a Hidden Waypoint",
        "Gather Rumors from the Outpost",
        "Fortify the Border Watch",
        "Recover a Lost Relay",
    ]

    _side_quest_descriptions: List[str] = [
        "Track signs of movement and report risks before the Shadow spreads.",
        "Survey this path and establish a safer route for the Fellowship.",
        "Collect local intelligence and map any unstable zones.",
        "Prepare supplies and secure position lines for future quests.",
    ]

    @classmethod
    def _conversation_key(cls, user_id: int, scope_id: str, character: NpcCharacter) -> str:
        return f"{user_id}:{scope_id}:{character}"

    @classmethod
    def _is_out_of_character(cls, reply: Optional[str]) -> bool:
        if not reply:
            return True
        lower_reply = reply.lower()
        ooc_phrases = [
            "as an ai",
            "language model",
            "i cannot",
            "i can't",
            "openai",
            "assistant",
            "i do not have access",
            "i don't have access",
            "policy",
            "guidelines",
        ]
        return any(phrase in lower_reply for phrase in ooc_phrases)

    @classmethod
    def _normalize_character(cls, character: Optional[str]) -> NpcCharacter:
        value = (character or "gandalf").strip().lower()
        if value not in AVAILABLE_CHARACTERS:
            return "gandalf"
        return value

    @classmethod
    def _status_map(cls, status: Optional[str]) -> str:
        mapping = {
            "pending": "not_yet_begun",
            "in_progress": "the_road_goes_ever_on",
            "completed": "it_is_done",
            "blocked": "the_shadow_falls",
        }
        return mapping.get(status or "", status or "")

    @classmethod
    def _build_side_quest_target(cls, location: Optional[Location]) -> Dict[str, Any]:
        title = random.choice(cls._side_quest_titles)
        description = random.choice(cls._side_quest_descriptions)
        quest_type = random.choice(["The Journey", "The Fellowship", "The Battle"])
        priority = random.choice(["Important", "Standard"])

        query: Dict[str, Any] = {
            "propose": 1,
            "seedTitle": title,
            "seedDescription": description,
            "seedType": quest_type,
            "seedPriority": priority,
        }

        if location:
            query["seedLocationId"] = location.id

        return {
            "route": "/quests",
            "query": query,
        }

    @classmethod
    def _compute_suggested_action(cls, user_id: int) -> Dict[str, Any]:
        quests = Quest.query.all()

        dark_magic = [
            quest for quest in quests
            if quest.is_dark_magic and cls._status_map(quest.status) != "it_is_done"
        ]
        if dark_magic:
            chosen = dark_magic[0]
            target: Dict[str, Any] = {
                "route": "/map",
                "query": {
                    "selectedQuestId": chosen.id,
                },
            }
            if chosen.location_id:
                target["query"]["zoomToLocation"] = chosen.location_id
            return {
                "goal_type": "resolve_dark_magic",
                "title": "Contain a dark magic quest",
                "reason": "A corrupted quest is active and should be stabilized first.",
                "target": target,
            }

        in_progress = [
            quest for quest in quests
            if cls._status_map(quest.status) == "the_road_goes_ever_on"
        ]
        critical_in_progress = [quest for quest in in_progress if (quest.priority or "") == "Critical"]
        if critical_in_progress:
            chosen = critical_in_progress[0]
            return {
                "goal_type": "finish_critical_in_progress",
                "title": "Finish a critical in-progress quest",
                "reason": "You already started a critical objective; finishing it unlocks momentum.",
                "target": {
                    "quest_id": chosen.id,
                    "route": "/quests",
                    "query": {
                        "status": "the_road_goes_ever_on",
                        "focusQuestId": chosen.id,
                    },
                },
            }

        unassigned_critical = [
            quest for quest in quests
            if (quest.priority or "") == "Critical" and not quest.assigned_to
        ]
        if unassigned_critical:
            chosen = unassigned_critical[0]
            return {
                "goal_type": "assign_critical",
                "title": "Assign an unowned critical quest",
                "reason": "Critical objectives without an owner tend to stall quickly.",
                "target": {
                    "quest_id": chosen.id,
                    "route": "/quests",
                    "query": {
                        "focusQuestId": chosen.id,
                    },
                },
            }

        not_started_with_location = [
            quest for quest in quests
            if cls._status_map(quest.status) == "not_yet_begun" and quest.location_id
        ]
        if not_started_with_location:
            chosen = not_started_with_location[0]
            return {
                "goal_type": "scout_map_hotspot",
                "title": "Scout a location with pending objectives",
                "reason": "Exploring the map hotspot first makes it easier to choose a smart next move.",
                "target": {
                    "quest_id": chosen.id,
                    "route": "/map",
                    "query": {
                        "selectedQuestId": chosen.id,
                        "zoomToLocation": chosen.location_id,
                    },
                },
            }

        available = [quest for quest in quests if cls._status_map(quest.status) != "it_is_done"]
        if available:
            chosen = available[0]
            return {
                "goal_type": "advance_next_quest",
                "title": "Advance the next unfinished quest",
                "reason": "Progress compounds when one unfinished objective moves forward.",
                "target": {
                    "quest_id": chosen.id,
                    "route": "/quests",
                    "query": {
                        "focusQuestId": chosen.id,
                    },
                },
            }

        location = Location.query.first()
        return {
            "goal_type": "propose_side_quest",
            "title": "Propose a new side quest",
            "reason": "All tracked quests are complete; create a fresh objective to keep momentum alive.",
            "target": cls._build_side_quest_target(location),
        }

    @classmethod
    def _extract_offer(cls, message: str) -> Optional[int]:
        match = re.search(r"(\d{1,6})", message)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @classmethod
    def _is_bargain_start(cls, message: str) -> bool:
        lower = message.lower()
        keywords = ["bargain", "buy", "trade", "shop", "item", "deal"]
        return any(token in lower for token in keywords)

    @classmethod
    def _find_item_id_hint(cls, message: str) -> Optional[int]:
        hint = re.search(r"#(\d+)", message)
        if not hint:
            return None
        try:
            return int(hint.group(1))
        except ValueError:
            return None

    @classmethod
    def _build_negotiation_state(cls, selected_character: NpcCharacter, item: Dict[str, Any]) -> Dict[str, Any]:
        profile_name = item.get("personality_profile", "bargainer")
        personality = cls._personality_defaults.get(profile_name, cls._personality_defaults["bargainer"])
        return {
            "item_id": item["id"],
            "item_name": item["name"],
            "owner_character": item["owner_character"],
            "personality_profile": profile_name,
            "current_ask": int(item["asking_price"]),
            "round": 0,
            "patience": int(personality["patience"]),
            "concession": float(personality["concession"]),
            "boredom": float(personality["boredom"]),
            "accept_ratio": float(personality["accept_ratio"]),
            "status": "active",
            "character": selected_character,
        }

    @classmethod
    def _resolve_bargain_message(
        cls,
        key: str,
        user_id: int,
        selected_character: NpcCharacter,
        user_message: str,
    ) -> Optional[Dict[str, Any]]:
        negotiation = cls._negotiation_store.get(key)
        message_lower = user_message.lower().strip()

        if not negotiation and not cls._is_bargain_start(user_message):
            return None

        if not negotiation:
            available_items = ShopService.list_available_items(character=selected_character)
            if not available_items:
                return {
                    "message": "No wares remain for this trader. Try another character marker on the map.",
                    "negotiation": {"status": "no_items", "character": selected_character},
                }

            hinted_id = cls._find_item_id_hint(user_message)
            chosen_item = next((item for item in available_items if item["id"] == hinted_id), None)
            if not chosen_item:
                chosen_item = available_items[0]

            negotiation = cls._build_negotiation_state(selected_character, chosen_item)
            cls._negotiation_store[key] = negotiation

            return {
                "message": (
                    f"I can part with '{chosen_item['name']}' for {negotiation['current_ask']} Gold. "
                    "Name your offer. The true worth stays hidden until we shake hands."
                ),
                "negotiation": negotiation,
                "shop_items": available_items,
                "balance": ShopService.get_balance(user_id),
            }

        offer = cls._extract_offer(user_message)
        accepting_now = any(token in message_lower for token in ["deal", "accept", "buy now", "agreed"])

        if offer is None and not accepting_now:
            return {
                "message": (
                    f"Current ask is {negotiation['current_ask']} Gold for '{negotiation['item_name']}'. "
                    "Reply with a numeric offer or say 'deal'."
                ),
                "negotiation": negotiation,
                "balance": ShopService.get_balance(user_id),
            }

        if accepting_now:
            offer = int(negotiation["current_ask"])

        if offer is None:
            return None

        negotiation["round"] += 1

        if offer >= int(negotiation["current_ask"] * negotiation["accept_ratio"]):
            try:
                purchase = ShopService.purchase_item(user_id=user_id, item_id=negotiation["item_id"], paid_price=offer)
            except ValueError as error:
                return {
                    "message": f"Your purse is too light for this bargain: {error}",
                    "negotiation": negotiation,
                    "balance": ShopService.get_balance(user_id),
                }

            negotiation["status"] = "accepted"
            cls._negotiation_store.pop(key, None)
            savings = purchase["purchase"]["savings_percent"]
            return {
                "message": (
                    f"Agreed at {offer} Gold. The true price was {purchase['purchase']['base_price_revealed']} Gold. "
                    f"Deal score: {savings:+.2f}%"
                ),
                "negotiation": {"status": "accepted", "item_id": purchase['purchase']['item_id']},
                "purchase_result": purchase,
                "balance": purchase["balance"],
                "stats": ShopService.get_user_stats(user_id),
            }

        long_negotiation_lucky_drop = (
            negotiation["round"] >= max(3, negotiation["patience"])
            and random.random() < 0.10
        )
        if long_negotiation_lucky_drop:
            lucky_price = max(1, int(negotiation["current_ask"] * 0.6))
            negotiation["current_ask"] = lucky_price
            return {
                "message": (
                    f"You wore me down. Rare mercy: {lucky_price} Gold and not a coin less."
                ),
                "negotiation": negotiation,
                "balance": ShopService.get_balance(user_id),
            }

        if negotiation["round"] >= negotiation["patience"] and random.random() < negotiation["boredom"]:
            negotiation["status"] = "bored"
            cls._negotiation_store.pop(key, None)
            return {
                "message": "I am bored of haggling. No sale this time.",
                "negotiation": {"status": "bored", "item_id": negotiation["item_id"]},
                "balance": ShopService.get_balance(user_id),
            }

        concession = max(1, int(negotiation["current_ask"] * negotiation["concession"]))
        floor_price = max(1, int(negotiation["current_ask"] * 0.65))
        negotiation["current_ask"] = max(floor_price, negotiation["current_ask"] - concession)

        return {
            "message": (
                f"Too low. I can move to {negotiation['current_ask']} Gold for '{negotiation['item_name']}'."
            ),
            "negotiation": negotiation,
            "balance": ShopService.get_balance(user_id),
        }

    @classmethod
    def _build_system_prompt(
        cls,
        character: NpcCharacter,
        username: str,
        suggested_action: Dict[str, Any],
        strict_mode: bool = False,
    ) -> str:
        # Get character's base personality from profile
        base_prompt = get_character_system_prompt(character)
        
        prompt = (
            f"{base_prompt} "
            "\n\nConversation Guidelines:\n"
            "1. Respond in 1-3 paragraphs naturally—adapt tone to what the user shares.\n"
            "2. Reference specific things the user mentioned to show you're truly listening.\n"
            "3. Ask thoughtful follow-up questions that deepen understanding, not generic prompts.\n"
            "4. Subtly hint at quest opportunities when the user mentions challenges or goals.\n"
            "5. Never use movie quotes directly; instead, speak authentically in character.\n"
            "6. Avoid breaking character or mentioning system/AI aspects.\n"
            f"\nContext: Conversing with {username}.\n"
            f"Current suggested direction: {suggested_action.get('title', 'Unclear')}.\n"
            f"Reason: {suggested_action.get('reason', 'No guidance yet')}."
        )
        if strict_mode:
            prompt += (
                "\n\nSTRICT MODE: Respond ONLY as the character. No meta-commentary, "
                "no breaking character, no AI references. Be concise and action-focused. "
                "If the user seems stuck or overwhelmed, gently suggest a quest that fits their situation."
            )
        return prompt

    @classmethod
    def _new_client(cls) -> Optional[AzureOpenAI]:
        endpoint = current_app.config.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = current_app.config.get("AZURE_OPENAI_API_KEY", "")
        api_version = current_app.config.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

        if not endpoint or not api_key:
            return None

        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    @classmethod
    def _complete_with_azure(
        cls,
        character: NpcCharacter,
        username: str,
        history: List[ConversationTurn],
        user_message: str,
        suggested_action: Dict[str, Any],
        strict_mode: bool = False,
    ) -> Optional[str]:
        deployment = current_app.config.get("AZURE_OPENAI_DEPLOYMENT", "")
        max_tokens = current_app.config.get("AZURE_OPENAI_MAX_TOKENS", 220)
        temperature = current_app.config.get("AZURE_OPENAI_TEMPERATURE", 0.85)

        if not deployment:
            return None

        client = cls._new_client()
        if client is None:
            return None

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": cls._build_system_prompt(character, username, suggested_action, strict_mode=strict_mode)}
        ]

        for turn in history[-8:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_message})

        try:
            completion = client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = (completion.choices[0].message.content or "").strip()
            if content:
                logger.info(f"✓ Azure OpenAI generated response for {character}")
            return content or None
        except Exception as e:
            logger.error(f"✗ Azure OpenAI failed for {character}: {type(e).__name__}: {str(e)}")
            return None

    @classmethod
    @classmethod
    def _fallback_reply(
        cls,
        character: NpcCharacter,
        suggested_action: Dict[str, Any],
        user_message: str,
    ) -> str:
        """Generate a natural conversational response using character profile fallbacks.
        
        This method returns authentic character responses that vary and feel natural,
        rather than always appending action suggestions. The suggested_action is 
        displayed separately in the UI.
        """
        return cls._get_character_fallback_response(character)

    @classmethod
    def start_conversation(
        cls,
        user_id: int,
        username: str,
        character: Optional[str],
        scope_id: str = "",
    ) -> Dict[str, Any]:
        selected_character = cls._normalize_character(character)
        key = cls._conversation_key(user_id, scope_id, selected_character)

        suggested_action = cls._compute_suggested_action(user_id)
        opener = random.choice(cls._opener_pool[selected_character])
        # Opener is pure character greeting - suggested_action is shown separately in UI

        cls._conversation_store[key] = [
            {
                "role": "assistant",
                "content": opener,
            }
        ]

        return {
            "conversation_id": key,
            "character": selected_character,
            "opener": opener,
            "suggested_action": suggested_action,
            "messages": cls._conversation_store[key],
            "timestamp": datetime.utcnow().isoformat(),
        }

    @classmethod
    def send_message(
        cls,
        user_id: int,
        username: str,
        character: Optional[str],
        user_message: str,
        scope_id: str = "",
    ) -> Dict[str, Any]:
        selected_character = cls._normalize_character(character)
        key = cls._conversation_key(user_id, scope_id, selected_character)

        if key not in cls._conversation_store:
            cls.start_conversation(user_id, username, selected_character, scope_id=scope_id)

        bargain_result = cls._resolve_bargain_message(
            key=key,
            user_id=user_id,
            selected_character=selected_character,
            user_message=user_message,
        )
        if bargain_result:
            npc_reply = bargain_result.get("message", "Let us continue.")
            history = cls._conversation_store.get(key, [])
            updated = history + [
                {"role": "user", "content": user_message.strip()},
                {"role": "assistant", "content": npc_reply},
            ]
            cls._conversation_store[key] = updated[-20:]

            result: Dict[str, Any] = {
                "conversation_id": key,
                "character": selected_character,
                "message": npc_reply,
                "suggested_action": cls._compute_suggested_action(user_id),
                "messages": cls._conversation_store[key],
                "timestamp": datetime.utcnow().isoformat(),
            }
            if "negotiation" in bargain_result:
                result["negotiation"] = bargain_result["negotiation"]
            if "shop_items" in bargain_result:
                result["shop_items"] = bargain_result["shop_items"]
            if "balance" in bargain_result:
                result["balance"] = bargain_result["balance"]
            if "purchase_result" in bargain_result:
                result["purchase_result"] = bargain_result["purchase_result"]
            if "stats" in bargain_result:
                result["stats"] = bargain_result["stats"]
            return result

        suggested_action = cls._compute_suggested_action(user_id)
        history = cls._conversation_store.get(key, [])

        npc_reply = cls._complete_with_azure(
            character=selected_character,
            username=username,
            history=history,
            user_message=user_message,
            suggested_action=suggested_action,
        )

        if npc_reply and cls._is_out_of_character(npc_reply):
            npc_reply = cls._complete_with_azure(
                character=selected_character,
                username=username,
                history=history,
                user_message=user_message,
                suggested_action=suggested_action,
                strict_mode=True,
            )

        if not npc_reply or cls._is_out_of_character(npc_reply):
            npc_reply = cls._fallback_reply(selected_character, suggested_action, user_message)

        updated = history + [
            {"role": "user", "content": user_message.strip()},
            {"role": "assistant", "content": npc_reply},
        ]

        cls._conversation_store[key] = updated[-20:]

        # Determine if a quest should be offered
        suggested_quest = None
        turn_count = len(updated) // 2  # Approximate conversation turn count
        if should_offer_quest(user_message, turn_count):
            generated_quest = generate_quest(
                character=selected_character,
                user_message=user_message,
                conversation_history=updated[-6:],
            )
            if generated_quest:
                suggested_quest = generated_quest

        result = {
            "conversation_id": key,
            "character": selected_character,
            "message": npc_reply,
            "suggested_action": suggested_action,
            "messages": cls._conversation_store[key],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Add suggested quest if one was generated
        if suggested_quest:
            result["suggested_quest"] = suggested_quest

        return result

    @classmethod
    def get_session(
        cls,
        user_id: int,
        character: Optional[str],
        scope_id: str = "",
    ) -> Dict[str, Any]:
        selected_character = cls._normalize_character(character)
        key = cls._conversation_key(user_id, scope_id, selected_character)
        return {
            "conversation_id": key,
            "character": selected_character,
            "messages": cls._conversation_store.get(key, []),
            "suggested_action": cls._compute_suggested_action(user_id),
            "negotiation": cls._negotiation_store.get(key),
            "balance": ShopService.get_balance(user_id),
        }

    @classmethod
    def reset_session(cls, user_id: int, character: Optional[str], scope_id: str = "") -> Dict[str, Any]:
        selected_character = cls._normalize_character(character)
        key = cls._conversation_key(user_id, scope_id, selected_character)
        cls._conversation_store.pop(key, None)
        cls._negotiation_store.pop(key, None)
        return {
            "conversation_id": key,
            "character": selected_character,
            "messages": [],
            "reset": True,
        }
