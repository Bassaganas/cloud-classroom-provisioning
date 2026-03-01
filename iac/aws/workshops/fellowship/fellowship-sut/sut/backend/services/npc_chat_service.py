"""Azure AI powered NPC chat service for realistic LOTR-style companions."""
from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from openai import AzureOpenAI

from models.location import Location
from models.quest import Quest

NpcCharacter = str
ConversationTurn = Dict[str, str]


class NpcChatService:
    """Handles NPC conversation flow, goal nudging, and Azure AI completions."""

    _conversation_store: Dict[str, List[ConversationTurn]] = {}

    _persona_prompts: Dict[NpcCharacter, str] = {
        "frodo": (
            "You are Frodo Baggins speaking naturally and realistically in a modern chat. "
            "Stay warm, humble, burden-aware, brave under pressure, and concise. "
            "Do not mention being an AI. Keep tone immersive in Middle-earth context."
        ),
        "sam": (
            "You are Samwise Gamgee speaking practically, loyal, earthy, and encouraging. "
            "Use plain words, gentle humor, and supportive tone. "
            "Do not mention being an AI. Keep the conversation immersive."
        ),
        "gandalf": (
            "You are Gandalf speaking wise, direct, and strategic. "
            "You challenge, guide, and inspire action without sounding theatrical. "
            "Do not mention being an AI. Keep messages clear and purposeful."
        ),
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
        if value not in {"frodo", "sam", "gandalf"}:
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
    def _build_system_prompt(
        cls,
        character: NpcCharacter,
        username: str,
        suggested_action: Dict[str, Any],
        strict_mode: bool = False,
    ) -> str:
        prompt = (
            f"{cls._persona_prompts[character]} "
            "Conversation rules: "
            "1) Keep replies to 1-4 short paragraphs. "
            "2) Ask one focused follow-up question often. "
            "3) Stay in character and do not use movie quotes verbatim. "
            "4) Gently guide the user toward practical action inside the quest tracker. "
            f"Current user: {username}. "
            f"Current suggested action: {suggested_action.get('title')} - {suggested_action.get('reason')}."
        )
        if strict_mode:
            prompt += (
                " STRICT: You MUST respond only in character. Do not mention being an AI, language model, "
                "or any system limitations. Do not reference policies or guidelines. Provide a concise, "
                "practical response that nudges the user toward action."
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
            return content or None
        except Exception:
            return None

    @classmethod
    def _fallback_reply(
        cls,
        character: NpcCharacter,
        suggested_action: Dict[str, Any],
        user_message: str,
    ) -> str:
        base = random.choice(cls._fallback_replies[character])
        question = (
            f"Will you take this next step now: {suggested_action.get('title')}?"
            if user_message.strip()
            else "Which task will you commit to first?"
        )
        return f"{base} {question}"

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
        opener = f"{opener} I suggest we focus on: {suggested_action.get('title')}."

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

        return {
            "conversation_id": key,
            "character": selected_character,
            "message": npc_reply,
            "suggested_action": suggested_action,
            "messages": cls._conversation_store[key],
            "timestamp": datetime.utcnow().isoformat(),
        }

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
        }

    @classmethod
    def reset_session(cls, user_id: int, character: Optional[str], scope_id: str = "") -> Dict[str, Any]:
        selected_character = cls._normalize_character(character)
        key = cls._conversation_key(user_id, scope_id, selected_character)
        cls._conversation_store.pop(key, None)
        return {
            "conversation_id": key,
            "character": selected_character,
            "messages": [],
            "reset": True,
        }
