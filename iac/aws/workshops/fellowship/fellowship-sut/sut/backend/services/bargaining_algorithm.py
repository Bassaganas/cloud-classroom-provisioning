"""Bargaining algorithm for NPC negotiation."""
from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class NegotiationResult(str, Enum):
    """Possible outcomes of a negotiation."""
    COUNTER_OFFER = "counter-offer"
    OFFER_ACCEPTED = "offer-accepted"
    OFFER_REJECTED = "offer-rejected"
    STOP_BARGAIN = "stop-bargain"


class BargainingAlgorithm:
    """
    Hybrid bargaining algorithm that evaluates user offers based on character traits.
    
    Algorithm evaluates:
    - Character personality (patience, concession rate, boredom threshold, accept ratio)
    - Current mood (affected by user actions)
    - External events (randomness factor)
    - Flattery detection (user behavior trigger)
    - Round count (max rounds per character)
    """

    # Default personality profiles indexed by character
    PERSONALITY_PROFILES = {
        "frodo": {
            "patience": 5,
            "concession": 0.12,
            "boredom": 0.08,
            "accept_ratio": 0.92,
            "max_rounds": 6,
            "generosity_on_flatter": 0.05,  # 5% better offer when flattered
        },
        "sam": {
            "patience": 4,
            "concession": 0.10,
            "boredom": 0.10,
            "accept_ratio": 0.95,
            "max_rounds": 5,
            "generosity_on_flatter": 0.04,
        },
        "gandalf": {
            "patience": 6,
            "concession": 0.15,
            "boredom": 0.05,
            "accept_ratio": 0.90,
            "max_rounds": 7,
            "generosity_on_flatter": 0.06,
        },
    }

    @classmethod
    def evaluate_offer(
        cls,
        user_offer: int,
        current_ask: int,
        character: str,
        round_num: int,
        is_flattered: bool = False,
        mood_modifiers: Optional[Dict[str, float]] = None,
        user_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a user's offer or message against the NPC's negotiation state.

        Args:
            user_offer: The amount offered by the user
            current_ask: The NPC's current asking price
            character: The NPC character name
            round_num: Current negotiation round (0-based)
            is_flattered: Whether the user flattered the character
            mood_modifiers: Optional mood adjustments (e.g., {"patience": -1, "boredom": +0.1})
            user_message: The raw user message (for 'deal' detection)

        Returns:
            Dict containing:
            - result: NegotiationResult enum value
            - counter_offer: New ask price (if counter-offer)
            - context: Debug context about the decision
        """
        profile = cls.PERSONALITY_PROFILES.get(character, cls.PERSONALITY_PROFILES["gandalf"])

        # Apply mood modifiers if provided
        patience = profile["patience"]
        boredom = profile["boredom"]

        if mood_modifiers:
            patience += mood_modifiers.get("patience", 0)
            boredom += mood_modifiers.get("boredom", 0)
            boredom = max(0, min(1, boredom))  # Clamp to [0, 1]

        # If user says 'deal', accept at current ask
        if user_message and user_message.strip().lower() in {"deal", "i'll take it", "i will take it", "buy", "buy it", "accept"}:
            return {
                "result": NegotiationResult.OFFER_ACCEPTED,
                "counter_offer": None,
                "context": {
                    "reason": "user_said_deal",
                    "user_offer": user_offer,
                    "current_ask": current_ask,
                },
            }

        # Check if max rounds exceeded
        if round_num >= profile["max_rounds"]:
            return {
                "result": NegotiationResult.STOP_BARGAIN,
                "counter_offer": None,
                "context": {
                    "reason": "max_rounds_exceeded",
                    "round_num": round_num,
                    "max_rounds": profile["max_rounds"],
                },
            }

        # Calculate acceptance threshold
        # Flattered characters are slightly more generous
        accept_ratio = profile["accept_ratio"]
        if is_flattered:
            accept_ratio -= profile["generosity_on_flatter"]

        # Check if offer is acceptable
        if user_offer >= int(current_ask * accept_ratio):
            return {
                "result": NegotiationResult.OFFER_ACCEPTED,
                "counter_offer": None,
                "context": {
                    "reason": "offer_acceptable",
                    "user_offer": user_offer,
                    "threshold": int(current_ask * accept_ratio),
                    "is_flattered": is_flattered,
                },
            }

        # Check for lucky drop (long negotiation can result in sudden price drop)
        long_negotiation_threshold = max(3, patience)
        if round_num >= long_negotiation_threshold and random.random() < 0.10:
            lucky_price = max(user_offer, int(current_ask * 0.60))
            return {
                "result": NegotiationResult.COUNTER_OFFER,
                "counter_offer": lucky_price,
                "context": {
                    "reason": "lucky_drop",
                    "round_num": round_num,
                    "patience_threshold": long_negotiation_threshold,
                    "message_hint": "user_wore_down_character",
                },
            }

        # Check if character is bored and refuses
        if round_num >= patience and random.random() < boredom:
            return {
                "result": NegotiationResult.STOP_BARGAIN,
                "counter_offer": None,
                "context": {
                    "reason": "boredom_threshold",
                    "round_num": round_num,
                    "patience": patience,
                    "boredom_roll": boredom,
                },
            }

        # Counter-offer: concede a bit, but never below user's offer
        concession_amount = max(1, int(current_ask * profile["concession"]))
        floor_price = max(user_offer, int(current_ask * 0.65))  # Don't go below user's offer or 65% of current ask
        new_ask = max(floor_price, current_ask - concession_amount)

        return {
            "result": NegotiationResult.COUNTER_OFFER,
            "counter_offer": new_ask,
            "context": {
                "reason": "counter_offer",
                "round_num": round_num,
                "original_ask": current_ask,
                "concession_amount": concession_amount,
                "floor_price": floor_price,
                "is_flattered": is_flattered,
                "user_offer": user_offer,
            },
        }

    @classmethod
    def detect_flattery(cls, user_message: str) -> bool:
        """
        Detect flattery in user's message.
        
        Looks for phrases indicating compliments, admiration, or flattery.
        This is visible to backend only; LLM can add more sophisticated detection.
        """
        message_lower = user_message.lower().strip()
        
        flattery_keywords = [
            "amazing",
            "beautiful",
            "brave",
            "brilliant",
            "clever",
            "exceptional",
            "excellent",
            "extraordinary",
            "fabulous",
            "fantastic",
            "fine",
            "glorious",
            "graceful",
            "great",
            "handsome",
            "impressive",
            "incredible",
            "intelligent",
            "magnificent",
            "marvelous",
            "noble",
            "outstanding",
            "powerful",
            "remarkable",
            "skilled",
            "splendid",
            "superb",
            "talented",
            "tremendous",
            "wonderful",
            "you are",
            "you're",
            "you seem",
            "that's great",
            "that's amazing",
            "i admire",
            "i respect",
            "very wise",
            "very kind",
            "very clever",
            "very brave",
        ]
        
        # Simple keyword matching
        return any(keyword in message_lower for keyword in flattery_keywords)

    @classmethod
    def calculate_mood_change(
        cls,
        previous_offer: Optional[int],
        current_offer: int,
        current_ask: int,
    ) -> Dict[str, float]:
        """
        Calculate mood changes based on user actions.
        
        Returns mood modifiers that should be applied to the negotiation profile.
        
        Examples:
        - Repeated very low offers -> negative mood (more patient but bored)
        - Fair offers -> positive mood
        - Rapidly increasing offers -> positive mood
        """
        modifiers = {}
        
        if previous_offer is not None:
            offer_delta = current_offer - previous_offer
            offer_ratio = current_offer / current_ask if current_ask > 0 else 0
            
            # If user is insultingly low (< 30% of ask), character gets annoyed
            if offer_ratio < 0.30:
                modifiers["boredom"] = 0.05  # Increases boredom
                modifiers["patience"] = -1   # Decreases patience
            # If offer is fair (50-80% of ask), character is encouraged
            elif 0.50 <= offer_ratio <= 0.80:
                modifiers["boredom"] = -0.03  # Decreases boredom
            # If user is increasing offers, character is pleased
            elif offer_delta > 0:
                modifiers["boredom"] = -0.02
        
        return modifiers

    @classmethod
    def get_summary_for_llm(
        cls,
        negotiation_state: Dict[str, Any],
        algorithm_result: Dict[str, Any],
        user_offer: int,
        character_personality: str,
        is_flattered: bool,
        mood_modifiers: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Generate a JSON summary to pass to the LLM for natural language generation.
        
        Only includes relevant fields for the current negotiation turn.
        """
        profile = cls.PERSONALITY_PROFILES.get(
            negotiation_state.get("character", "gandalf"),
            cls.PERSONALITY_PROFILES["gandalf"]
        )
        
        summary: Dict[str, Any] = {
            "character": negotiation_state.get("character"),
            "item_name": negotiation_state.get("item_name"),
            "item_id": negotiation_state.get("item_id"),
            "original_price": negotiation_state.get("original_price"),
            "current_ask": negotiation_state.get("current_ask"),
            "user_offer": user_offer,
            "round": negotiation_state.get("round"),
            "character_personality_type": character_personality,
            "is_flattered": is_flattered,
        }
        
        # Add algorithm result based on type
        result_type = algorithm_result.get("result")
        if result_type == NegotiationResult.COUNTER_OFFER:
            summary["negotiation_result"] = "counter-offer"
            summary["counter_offer"] = algorithm_result.get("counter_offer")
        elif result_type == NegotiationResult.OFFER_ACCEPTED:
            summary["negotiation_result"] = "offer-accepted"
        elif result_type == NegotiationResult.OFFER_REJECTED:
            summary["negotiation_result"] = "offer-rejected"
        elif result_type == NegotiationResult.STOP_BARGAIN:
            summary["negotiation_result"] = "stop-bargain"
            summary["stop_reason"] = algorithm_result.get("context", {}).get("reason")
        
        # Add mood context if modifiers present
        if mood_modifiers:
            summary["mood_context"] = mood_modifiers
        
        # Only include negotiation_style if applicable
        if "negotiation_style" in negotiation_state:
            summary["user_negotiation_style"] = negotiation_state["negotiation_style"]
        
        return summary
