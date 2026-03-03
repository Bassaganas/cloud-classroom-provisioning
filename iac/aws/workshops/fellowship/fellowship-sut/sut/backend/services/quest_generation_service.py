"""Quest generation service for NPC-driven quest creation.

Generates semantically coherent, character-appropriate quests based on:
- NPC character personality
- Conversation context
- LOTR theme adherence
"""

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from openai import AzureOpenAI

from models.location import Location
from services.character_profiles import get_character_profile, get_quest_affinity

# Configure logging
logger = logging.getLogger(__name__)

# Quest generation templates organized by NPC
QUEST_GENERATION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "frodo": {
        "contexts": [
            "The user mentions a problem or burden they're carrying.",
            "The user asks for guidance on what to do next.",
            "The user seems overwhelmed by many tasks.",
        ],
        "themes": [
            "Hidden paths and solutions",
            "Understanding the true nature of a problem",
            "Journeys to unfamiliar places",
            "Tests of character and courage",
        ],
        "title_seeds": [
            "Uncover the {nature} of {subject}",
            "Journey to {location} and discover {objective}",
            "Face your doubt about {challenge}",
            "Find the hidden wisdom in {situation}",
        ],
        "types": ["The Journey", "The Fellowship", "The Ring"],
        "priorities": ["Important", "Critical"],
    },
    "sam": {
        "contexts": [
            "The user has completed something and needs momentum.",
            "The user asks for practical help or advice.",
            "The user seems stuck and needs encouragement.",
        ],
        "themes": [
            "Building and creating",
            "Practical problem-solving",
            "Loyalty and companionship",
            "Caring for others or a place",
        ],
        "title_seeds": [
            "Prepare {place} for {purpose}",
            "Build or fix {object} for {reason}",
            "Gather supplies: {list}",
            "Care for {person_or_place} by {action}",
        ],
        "types": ["The Fellowship", "The Battle", "The Journey"],
        "priorities": ["Important", "Standard"],
    },
    "gandalf": {
        "contexts": [
            "The user has reached a critical decision point.",
            "The user is avoiding an important choice.",
            "The user asks for strategic guidance.",
        ],
        "themes": [
            "Strategic choices with large consequences",
            "Testing someone's resolve or wisdom",
            "Understanding larger patterns",
            "Containing or confronting darkness",
        ],
        "title_seeds": [
            "Decide the fate of {stakes}",
            "Confront {threat} before it spreads",
            "Understand the pattern of {mystery}",
            "Test your resolve: {challenge}",
        ],
        "types": ["The Ring", "Dark Magic", "The Battle"],
        "priorities": ["Critical", "Important"],
    },
}

# Fallback quest generation (no AI)
FALLBACK_QUESTS: Dict[str, List[Dict[str, Any]]] = {
    "frodo": [
        {
            "title": "Discover the Heart of the Matter",
            "description": "Consider this problem deeply: what lies at its true center? It may appear different when you understand its nature.",
            "quest_type": "The Journey",
            "priority": "Important",
        },
        {
            "title": "Walk the Hidden Path",
            "description": "Every great challenge has an unexpected approach. Take time to find the unconventional route forward.",
            "quest_type": "The Fellowship",
            "priority": "Important",
        },
        {
            "title": "Test Your Courage",
            "description": "Sometimes the next step demands we face what we've been avoiding. What fear guards your path?",
            "quest_type": "The Ring",
            "priority": "Critical",
        },
    ],
    "sam": [
        {
            "title": "Prepare the Ground",
            "description": "Good work starts with preparation. Gather what you need and organize it well before beginning.",
            "quest_type": "The Fellowship",
            "priority": "Important",
        },
        {
            "title": "Strengthen Your Bonds",
            "description": "Reach out and help a companion with something they're struggling with. Loyalty matters.",
            "quest_type": "The Fellowship",
            "priority": "Standard",
        },
        {
            "title": "Build Something That Lasts",
            "description": "Create or improve something that will help you and others in the times ahead.",
            "quest_type": "The Battle",
            "priority": "Important",
        },
    ],
    "gandalf": [
        {
            "title": "Recognize the Pattern",
            "description": "Step back and observe the larger picture. What do the recent events tell you about the true state of affairs?",
            "quest_type": "The Ring",
            "priority": "Critical",
        },
        {
            "title": "Make the Hard Choice",
            "description": "A decision looms that cannot be avoided. Choose based on principle, not comfort.",
            "quest_type": "The Ring",
            "priority": "Critical",
        },
        {
            "title": "Confront the Advancing Shadow",
            "description": "A threat grows. Take action now before it becomes unstoppable.",
            "quest_type": "Dark Magic",
            "priority": "Critical",
        },
    ],
}


# Middle-earth locations mapping (case-insensitive)
MIDDLE_EARTH_LOCATIONS: Dict[str, List[str]] = {
    "Rivendell": ["rivendell", "elrond's home", "valley of imladris", "imladris"],
    "Lothlórien": ["lothlórien", "lothlórien", "golden wood", "caras galadhon"],
    "Moria": ["moria", "khazad-dum", "dwarf kingdom", "mines of moria"],
    "Mordor": ["mordor", "sauron's realm", "mount doom", "barad-dûr"],
    "Rohan": ["rohan", "rolling plains", "mark", "edoras"],
    "Gondor": ["gondor", "minas tirith", "white city", "kingdom of men"],
    "The Shire": ["the shire", "shire", "hobbiton", "bag end"],
    "Isengard": ["isengard", "orthanc", "wizard's tower"],
    "Mirkwood": ["mirkwood", "greenwood", "thranduil", "wood-elves"],
    "Lake-town": ["lake-town", "esgaroth", "bard", "barrel rider"],
    "The Grey Havens": ["grey havens", "grey havens", "valinor", "undying lands", "sailing west"],
    "Erebor": ["erebor", "lonely mountain", "dwarf kingdom"],
    "The Grey Mountains": ["grey mountains", "misty mountains", "mountains"],
}


def _find_location_by_text(text: str) -> Optional[Tuple[str, int]]:
    """Extract and find a location from text.
    
    Searches through MIDDLE_EARTH_LOCATIONS and the database to find mentions.
    Returns the Location name and ID that was mentioned in the text.
    
    Args:
        text: Text to search for location mentions
    
    Returns:
        Tuple of (location_name, location_id) or None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Search by known aliases
    for location_name, aliases in MIDDLE_EARTH_LOCATIONS.items():
        for alias in aliases:
            if alias in text_lower:
                # Try to find this location in database
                try:
                    location = Location.query.filter_by(name=location_name).first()
                    if location:
                        return (location_name, location.id)
                except Exception as e:
                    logger.warning(f"Failed to query location {location_name}: {e}")
                    return (location_name, None)
    
    return None


def _add_location_to_quest(quest: Dict[str, Any]) -> Dict[str, Any]:
    """Add location_id to a quest based on location mention in description.
    
    Searches the quest description for Middle-earth location mentions
    and adds location_id if found.
    
    Args:
        quest: Quest dict with title, description, quest_type, priority
    
    Returns:
        Same quest dict with optional location_id added
    """
    if not quest.get("description"):
        return quest
    
    location_result = _find_location_by_text(quest["description"])
    if location_result:
        location_name, location_id = location_result
        if location_id:
            quest["location_id"] = location_id
            logger.debug(f"✓ Assigned location '{location_name}' (ID: {location_id}) to quest")
    
    return quest


def _new_azure_client() -> Optional[AzureOpenAI]:
    """Create Azure OpenAI client if configured."""
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


def _generate_quest_with_ai(
    character: str,
    user_message: str,
    conversation_history: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """Generate a quest using Azure OpenAI.
    
    Args:
        character: NPC character (frodo, sam, gandalf)
        user_message: User's latest message
        conversation_history: Recent conversation turns
    
    Returns:
        Generated quest dict or None if AI fails
    """
    deployment = current_app.config.get("AZURE_OPENAI_DEPLOYMENT", "")
    if not deployment:
        return None

    client = _new_azure_client()
    if client is None:
        return None

    profile = get_character_profile(character)
    quest_types = get_quest_affinity(character)

    # Build system prompt for quest generation with better context awareness
    character_context = ""
    if character == "frodo":
        character_context = (
            "Frodo speaks of quests related to the Ring, Mordor, journeys, and bearing burdens. "
            "He frames activities as part of a larger quest toward freedom. "
            "Suggest locations like 'Rivendell', 'Lothlórien', 'Moria', or 'Mordor'. "
        )
    elif character == "sam":
        character_context = (
            "Sam thinks in practical terms: building, preparing, defending, growing. "
            "He frames quests around making things better and stronger. "
            "Suggest locations like 'The Shire', 'Gondor', or 'The Grey Havens'. "
        )
    elif character == "gandalf":
        character_context = (
            "Gandalf sees the bigger strategic picture and long-term consequences. "
            "He frames quests as moves in a grand strategy against darkness. "
            "Suggest locations like 'Isengard', 'Orthanc', 'Moria', or 'The Grey Havens'. "
        )
    
    system_prompt = f"""You are {profile.get('full_name')}, {profile.get('title')}.

{character_context}

Your job: Create a quest that:
1. Directly ties to what the user just said in conversation
2. Feels authentic to {character}'s personality and way of thinking
3. Uses one of these quest types: {", ".join(quest_types)}
4. Is achievable yet substantial and meaningful
5. Is set in Middle-earth—suggest a specific location
6. Frames it in {character}'s voice and perspective

Respond with ONLY valid JSON (no markdown, no explanation):
{{
    "title": "Quest name (4-8 words, action-oriented)",
    "description": "2-3 sentences: (a) what the quest entails, (b) why it matters, (c) which location it involves",
    "quest_type": "{quest_types[0]}",
    "priority": "Important"
}}"""

    # Build conversation context with better preservation of dialogue flow
    messages = [{"role": "system", "content": system_prompt}]

    # Include last few turns to understand context
    for turn in conversation_history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Ask for quest based on the actual conversation, not just latest message
    context_summary = f"""Based on what I just heard, here's what stands out as a quest opportunity:
    
Latest from the user: "{user_message}"

Now, {profile.get('full_name')}, what quest would help them move forward?"""
    
    messages.append({"role": "user", "content": context_summary})

    try:
        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=300,
            temperature=0.8,
        )
        response_text = (completion.choices[0].message.content or "").strip()

        # Try to parse JSON
        quest_data = json.loads(response_text)

        # Validate required fields
        if all(k in quest_data for k in ["title", "description", "quest_type", "priority"]):
            # Add location to quest if mentioned in description
            quest_data = _add_location_to_quest(quest_data)
            logger.info(f"✓ Azure OpenAI generated quest for {character}")
            return quest_data

    except Exception as e:
        logger.error(f"✗ Quest generation failed for {character}: {type(e).__name__}: {str(e)}")
        pass

    return None


def generate_quest(
    character: str,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Generate a quest appropriate to the NPC character.
    
    Uses AI if available, falls back to templates + randomization.
    Always attempts to assign a location based on quest description.
    
    Args:
        character: NPC character (frodo, sam, gandalf)
        user_message: User's latest message
        conversation_history: Recent conversation turns (optional)
    
    Returns:
        Quest dict with title, description, quest_type, priority, and optional location_id
    """
    if not conversation_history:
        conversation_history = []

    # Try AI generation first
    ai_quest = _generate_quest_with_ai(character, user_message, conversation_history)
    if ai_quest:
        return ai_quest

    # Fall back to template-based generation
    if character not in FALLBACK_QUESTS:
        character = "gandalf"

    quest = random.choice(FALLBACK_QUESTS[character])
    
    # Add location to fallback quest too
    quest = _add_location_to_quest(quest)
    
    return quest


def should_offer_quest(user_message: str, conversation_turn_count: int = 0) -> bool:
    """Determine if this is a good moment to offer a quest.
    
    Offers quests when:
    - User seems to be looking for direction or action (keywords)
    - Early in conversation (turn 1-2) to set the tone
    - User asks for help explicitly
    - User seems stuck or overwhelmed
    
    Args:
        user_message: User's latest message
        conversation_turn_count: Number of turns in conversation
    
    Returns:
        True if a quest should be offered
    """
    message_lower = user_message.lower().strip()
    
    # Strong signals for quest readiness
    strong_keywords = [
        "help", "stuck", "what next", "what should", "can you suggest",
        "guide", "quest", "task", "challenge", "adventure", "action",
        "ready", "let's", "should we", "next step", "forward"
    ]
    has_strong_signal = any(kw in message_lower for kw in strong_keywords)
    
    # Softer signals (still valid but need turn count context)
    soft_keywords = ["do", "can", "shall", "would", "could", "problem"]
    has_soft_signal = any(kw in message_lower for kw in soft_keywords)
    
    # Never offer in the first turn (let conversation start naturally)
    if conversation_turn_count < 1:
        return False
    
    # Always offer if there's a strong signal
    if has_strong_signal:
        return True
    
    # Offer in early conversations even with soft signals
    if conversation_turn_count <= 2 and has_soft_signal:
        return True
    
    # Occasionally offer even without keywords (keep engagement)
    if conversation_turn_count == 2 and len(message_lower) > 10:
        return True

    return False
