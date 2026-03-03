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
from services.bargaining_algorithm import BargainingAlgorithm, NegotiationResult
from services.bargaining_config import BargainingConfig
from services.negotiation_logger import NegotiationLogger

# Configure logging
logger = logging.getLogger(__name__)

NpcCharacter = str
ConversationTurn = Dict[str, str]


class NpcChatService:
    """Handles NPC conversation flow, goal nudging, and Azure AI completions."""

    _conversation_store: Dict[str, List[ConversationTurn]] = {}
    _negotiation_store: Dict[str, Dict[str, Any]] = {}
    _negotiation_session_ids: Dict[str, str] = {}  # Maps conversation key to logger session ID
    _flattery_flags: Dict[str, bool] = {}  # Track if flattery bonus used in this negotiation

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
    def _build_bargain_llm_prompt(
        cls,
        character: NpcCharacter,
        negotiation_summary: Dict[str, Any],
    ) -> str:
        """
        Build the LLM prompt for bargaining negotiation.
        
        The LLM receives the algorithm's result and should:
        1. Rephrase and justify the result naturally
        2. Stay in character
        3. Acknowledge flattery if applicable
        4. Reference item qualities and in-world context
        5. Try to persuade user to accept the offer
        """
        char_profile = get_character_profile(character)
        personality_traits = ", ".join(char_profile.get("personality", []))
        
        result = negotiation_summary.get("negotiation_result", "")
        
        prompt = (
            f"You are {char_profile.get('full_name', character)}, a character in Middle-earth. "
            f"Your personality traits: {personality_traits}. "
            f"\n\nYou are negotiating over item: {negotiation_summary.get('item_name', 'an item')}. "
        )
        
        if negotiation_summary.get("is_flattered"):
            prompt += "\nThe user just flattered you—acknowledge this naturally and favorably. "
        
        if result == "counter-offer":
            counter = negotiation_summary.get("counter_offer")
            prompt += (
                f"\nYou are making a counter-offer of {counter} gold. "
                f"The user offered {negotiation_summary.get('user_offer')} gold (you originally asked {negotiation_summary.get('current_ask')}). "
                f"Justify this counter-offer, reference the item's importance to you, "
                f"and subtly persuade the user to accept. Stay brief (1-2 sentences). "
                f"Stay in character. Do NOT mention the negotiation mechanics or rounds."
            )
        elif result == "offer-accepted":
            prompt += (
                f"\nThe user's offer of {negotiation_summary.get('user_offer')} gold is acceptable! "
                f"Express satisfaction, perhaps acknowledge their negotiation skill, "
                f"and finalize the deal in character. Stay brief (1 sentence)."
            )
        elif result == "offer-rejected":
            prompt += (
                f"\nThe user's offer of {negotiation_summary.get('user_offer')} gold is too low. "
                f"You originally asked {negotiation_summary.get('current_ask')} gold. "
                f"Express disappointment or frustration (in character) and encourage them to do better. "
                f"Stay brief (1-2 sentences)."
            )
        elif result == "stop-bargain":
            stop_reason = negotiation_summary.get("stop_reason", "")
            if stop_reason == "boredom_threshold":
                prompt += (
                    f"\nYou are done haggling. You are bored and offended by this negotiation. "
                    f"Exit the negotiation angrily but in character. Stay brief (1 sentence). "
                    f"Do NOT offer further negotiation."
                )
            elif stop_reason == "max_rounds_exceeded":
                prompt += (
                    f"\nYou've spent enough time on this negotiation. "
                    f"Tell the user you're done discussing price and walk away in character. "
                    f"Stay brief (1 sentence)."
                )
        
        return prompt

    @classmethod
    def _complete_bargaining_with_llm(
        cls,
        character: NpcCharacter,
        negotiation_summary: Dict[str, Any],
    ) -> Optional[str]:
        """
        Generate a natural language response for bargaining using LLM.
        
        Takes the algorithm's structured result and asks LLM to generate
        an in-character response that justifies and rephrases it.
        """
        deployment = current_app.config.get("AZURE_OPENAI_DEPLOYMENT", "")
        if not deployment:
            return None

        client = cls._new_client()
        if client is None:
            return None

        prompt = cls._build_bargain_llm_prompt(character, negotiation_summary)
        
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"You are {negotiation_summary.get('character')}, a LOTR character. "
                    "Negotiate over items in-character, naturally and briefly. "
                    "Never break character or mention system details."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            max_tokens = current_app.config.get("AZURE_OPENAI_MAX_TOKENS", 150)
            temperature = current_app.config.get("AZURE_OPENAI_TEMPERATURE", 0.85)
            
            completion = client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            response = (completion.choices[0].message.content or "").strip()
            if response:
                logger.info(f"✓ Bargaining LLM generated response for {character}")
                
                # Log the LLM interaction
                session_id = cls._negotiation_session_ids.get(
                    f"{negotiation_summary.get('item_id')}:{character}"
                )
                if session_id:
                    NegotiationLogger.log_llm_interaction(
                        session_id=session_id,
                        llm_input_summary=negotiation_summary,
                        llm_output=response
                    )
            
            return response or None
        except Exception as e:
            logger.error(f"✗ Bargaining LLM failed for {character}: {type(e).__name__}: {str(e)}")
            return None

    @classmethod
    def _build_negotiation_state(cls, selected_character: NpcCharacter, item: Dict[str, Any]) -> Dict[str, Any]:
        profile_name = item.get("personality_profile", "bargainer")
        personality = cls._personality_defaults.get(profile_name, cls._personality_defaults["bargainer"])
        char_config = BargainingConfig.get_character_config(selected_character)
        max_rounds = int(char_config.get("max_rounds", int(personality["patience"])))
        return {
            "item_id": item["id"],
            "item_name": item["name"],
            "owner_character": item["owner_character"],
            "personality_profile": profile_name,
            "current_ask": int(item["asking_price"]),
            "round": 0,
            "patience": int(personality["patience"]),
            "max_rounds": max_rounds,
            "concession": float(personality["concession"]),
            "boredom": float(personality["boredom"]),
            "accept_ratio": float(personality["accept_ratio"]),
            "status": "active",
            "character": selected_character,
        }

    @classmethod
    @classmethod
    def _resolve_bargain_message(
        cls,
        key: str,
        user_id: int,
        selected_character: NpcCharacter,
        user_message: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a bargaining message using the hybrid algorithm + LLM approach.
        
        1. Algorithm evaluates the offer
        2. LLM generates natural language response
        3. Logs the negotiation
        """
        negotiation = cls._negotiation_store.get(key)
        message_lower = user_message.lower().strip()

        # Start bargaining if not already started
        if not negotiation and not cls._is_bargain_start(user_message):
            return None

        if not negotiation:
            # Initiate bargaining
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
            negotiation["original_price"] = int(chosen_item["asking_price"])
            cls._negotiation_store[key] = negotiation
            
            # Initialize negotiation logging
            session_id = NegotiationLogger.log_negotiation_start(
                character=selected_character,
                item_id=chosen_item["id"],
                item_name=chosen_item["name"],
                original_price=int(chosen_item["asking_price"])
            )
            cls._negotiation_session_ids[key] = session_id
            cls._flattery_flags[key] = False  # Initialize flattery flag

            return {
                "message": (
                    f"I can part with '{chosen_item['name']}' for {negotiation['current_ask']} Gold. "
                    "Name your offer. The true worth stays hidden until we shake hands."
                ),
                "negotiation": negotiation,
                "shop_items": available_items,
                "balance": ShopService.get_balance(user_id),
            }

        # Extract offer from message
        offer = cls._extract_offer(user_message)
        accepting_now = any(token in message_lower for token in ["deal", "accept", "buy now", "agreed"])

        # Validate that we have an offer
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

        # Log the offer
        session_id = cls._negotiation_session_ids.get(key)
        if session_id:
            NegotiationLogger.log_offer_made(
                session_id=session_id,
                round_num=negotiation["round"],
                user_offer=offer,
                current_ask=negotiation["current_ask"],
                is_flattered=cls._flattery_flags.get(key, False)
            )

        # Detect flattery
        is_flattered = (
            BargainingAlgorithm.detect_flattery(user_message)
            and not cls._flattery_flags.get(key, False)
        )
        
        if is_flattered:
            cls._flattery_flags[key] = True  # Mark flattery as used
            if session_id:
                NegotiationLogger.log_behavior_detected(session_id, "flattery")

        # Calculate mood modifiers based on user behavior
        previous_offer = negotiation.get("previous_offer")
        mood_modifiers = BargainingAlgorithm.calculate_mood_change(
            previous_offer=previous_offer,
            current_offer=offer,
            current_ask=negotiation["current_ask"]
        )
        
        negotiation["previous_offer"] = offer  # Track for next round
        negotiation["round"] += 1

        # Run bargaining algorithm
        algorithm_result = BargainingAlgorithm.evaluate_offer(
            user_offer=offer,
            current_ask=negotiation["current_ask"],
            character=selected_character,
            round_num=negotiation["round"],
            is_flattered=is_flattered,
            mood_modifiers=mood_modifiers if mood_modifiers else None
        )
        
        # Log algorithm result
        if session_id:
            NegotiationLogger.log_algorithm_result(
                session_id=session_id,
                result_type=algorithm_result["result"].value,
                context=algorithm_result["context"]
            )

        result_type = algorithm_result["result"]

        # Handle OFFER_ACCEPTED
        if result_type == NegotiationResult.OFFER_ACCEPTED:
            try:
                purchase = ShopService.purchase_item(
                    user_id=user_id,
                    item_id=negotiation["item_id"],
                    paid_price=offer
                )
            except ValueError as error:
                return {
                    "message": f"Your purse is too light for this bargain: {error}",
                    "negotiation": negotiation,
                    "balance": ShopService.get_balance(user_id),
                }

            negotiation["status"] = "accepted"
            cls._negotiation_store.pop(key, None)
            cls._flattery_flags.pop(key, None)
            
            # Log the successful negotiation
            if session_id:
                NegotiationLogger.log_negotiation_end(
                    session_id=session_id,
                    final_status="accepted",
                    final_price=offer,
                    rounds_taken=negotiation["round"]
                )
            
            # Generate LLM response
            summary = BargainingAlgorithm.get_summary_for_llm(
                negotiation_state={
                    "character": selected_character,
                    "item_name": negotiation["item_name"],
                    "item_id": negotiation["item_id"],
                    "original_price": negotiation.get("original_price", negotiation["current_ask"]),
                    "current_ask": negotiation["current_ask"],
                    "round": negotiation["round"],
                },
                algorithm_result=algorithm_result,
                user_offer=offer,
                character_personality=negotiation.get("personality_profile", "bargainer"),
                is_flattered=is_flattered,
                mood_modifiers=mood_modifiers or {}
            )
            
            npc_reply = cls._complete_bargaining_with_llm(selected_character, summary)
            if not npc_reply:
                npc_reply = f"Agreed at {offer} Gold. The true price was {purchase['purchase']['base_price_revealed']} Gold. Deal score: {purchase['purchase']['savings_percent']:+.2f}%"
            
            savings = purchase["purchase"]["savings_percent"]
            return {
                "message": npc_reply,
                "negotiation": {"status": "accepted", "item_id": purchase['purchase']['item_id']},
                "purchase_result": purchase,
                "balance": purchase["balance"],
                "stats": ShopService.get_user_stats(user_id),
            }

        # Handle STOP_BARGAIN
        elif result_type == NegotiationResult.STOP_BARGAIN:
            negotiation["status"] = "stop-bargain"
            cls._negotiation_store.pop(key, None)
            cls._flattery_flags.pop(key, None)
            
            # Log the stop
            stop_reason = algorithm_result["context"].get("reason", "unknown")
            if session_id:
                NegotiationLogger.log_negotiation_end(
                    session_id=session_id,
                    final_status="stopped",
                    final_price=None,
                    rounds_taken=negotiation["round"]
                )
            
            # Generate LLM response for stopping
            summary = BargainingAlgorithm.get_summary_for_llm(
                negotiation_state={
                    "character": selected_character,
                    "item_name": negotiation["item_name"],
                    "item_id": negotiation["item_id"],
                    "original_price": negotiation.get("original_price", negotiation["current_ask"]),
                    "current_ask": negotiation["current_ask"],
                    "round": negotiation["round"],
                },
                algorithm_result=algorithm_result,
                user_offer=offer,
                character_personality=negotiation.get("personality_profile", "bargainer"),
                is_flattered=is_flattered,
                mood_modifiers=mood_modifiers or {}
            )
            
            npc_reply = cls._complete_bargaining_with_llm(selected_character, summary)
            if not npc_reply:
                if stop_reason == "boredom_threshold":
                    npc_reply = "I am bored of haggling. No sale this time."
                else:
                    npc_reply = "We are finished haggling."
            
            return {
                "message": npc_reply,
                "negotiation": {"status": "stop-bargain", "item_id": negotiation["item_id"]},
                "balance": ShopService.get_balance(user_id),
            }

        # Handle COUNTER_OFFER
        elif result_type == NegotiationResult.COUNTER_OFFER:
            new_ask = algorithm_result["counter_offer"]
            negotiation["current_ask"] = new_ask
            
            # Generate LLM response for counter-offer
            summary = BargainingAlgorithm.get_summary_for_llm(
                negotiation_state={
                    "character": selected_character,
                    "item_name": negotiation["item_name"],
                    "item_id": negotiation["item_id"],
                    "original_price": negotiation.get("original_price", new_ask),
                    "current_ask": new_ask,
                    "round": negotiation["round"],
                },
                algorithm_result=algorithm_result,
                user_offer=offer,
                character_personality=negotiation.get("personality_profile", "bargainer"),
                is_flattered=is_flattered,
                mood_modifiers=mood_modifiers or {}
            )
            
            npc_reply = cls._complete_bargaining_with_llm(selected_character, summary)
            if not npc_reply:
                context = algorithm_result.get("context", {})
                if context.get("reason") == "lucky_drop":
                    npc_reply = f"You wore me down. Rare mercy: {new_ask} Gold and not a coin less."
                else:
                    npc_reply = (
                        f"Too low. I can move to {new_ask} Gold for '{negotiation['item_name']}'."
                    )
            
            return {
                "message": npc_reply,
                "negotiation": negotiation,
                "balance": ShopService.get_balance(user_id),
            }

        # Default fallback
        return {
            "message": "Let us continue our negotiation.",
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
