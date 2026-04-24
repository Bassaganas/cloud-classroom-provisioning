"""
Student identity generation utility for Fellowship provisioning.

Generates unique student identifiers using LOTR character names + short UUID suffix.
Format: {character_name}_{suffix} (e.g., legolas_xy37)

This utility ensures:
- Memorable, thematic student identifiers aligned with LOTR aesthetic
- Collision resistance via random UUID suffix
- Jenkins Groovy injection safety via regex validation
"""

import uuid
import random
from typing import Optional


# LOTR main + secondary character pool
LOTR_CHARACTERS = [
    # The Fellowship (main)
    "frodo",
    "samwise",
    "aragorn",
    "legolas",
    "gimli",
    "gandalf",
    # Secondary Fellowship members
    "boromir",
    "merry",
    "pippin",
    # Ring antagonists
    "sauron",
    "saruman",
    # Key allies
    "galadriel",
    "elrond",
    "lorien",
    "denethor",
    "theoden",
    "treebeard",
    "shelob",
    # Rohan warriors
    "eomer",
    "eowyn",
    # Dwarves
    "balin",
    "dori",
    "glorfindel",
    # Rivendell
    "arwen",
    "celeborn",
    # Moria/Mines
    "balrog",
    # Key NPCs from movies/books
    "bilbo",
    "smeagol",
    "gollum",
    "gothmog",
    "lurtz",
    "witch",
    "mouth",
    "beregond",
    "shadowfax",
    "grimbold",
]


def generate_short_uuid(length: int = 4) -> str:
    """
    Generate a short random UUID suffix.
    
    Args:
        length: Number of hex characters (default 4, ~65K combinations)
    
    Returns:
        Lowercase hex string of specified length
    """
    return uuid.uuid4().hex[:length].lower()


def validate_character_student_id(student_id: str) -> bool:
    """
    Validate student ID format against Jenkins Groovy injection safety.
    
    Regex: ^[a-z]+_[a-z0-9]{3,4}$
    - [a-z]+ : lowercase character name (no hyphens, underscores in name)
    - _ : literal separator
    - [a-z0-9]{3,4} : lowercase hex suffix (3-4 chars)
    
    This format prevents accidental Groovy code injection when substituted into
    Jenkins XML/Groovy templates.
    
    Args:
        student_id: Student identifier to validate
    
    Returns:
        True if valid format, False otherwise
    """
    import re
    pattern = r"^[a-z]+_[a-z0-9]{3,4}$"
    return bool(re.match(pattern, student_id))


def generate_character_student_id(character: Optional[str] = None, suffix_length: int = 4) -> str:
    """
    Generate a unique student identifier: {character}_{suffix}
    
    Args:
        character: Optional character name (lowercase). If not provided, random selection.
        suffix_length: Length of UUID suffix (default 4). Increase for more uniqueness if needed.
    
    Returns:
        Student identifier (e.g., "legolas_xy37")
    
    Raises:
        ValueError: If provided character is not in the LOTR character pool
    """
    # Select character
    if character is None:
        selected_char = random.choice(LOTR_CHARACTERS)
    else:
        char_lower = character.lower()
        if char_lower not in LOTR_CHARACTERS:
            raise ValueError(
                f"Character '{character}' not in LOTR pool. "
                f"Choose from: {', '.join(LOTR_CHARACTERS)}"
            )
        selected_char = char_lower
    
    # Generate suffix
    suffix = generate_short_uuid(suffix_length)
    
    # Format and validate
    student_id = f"{selected_char}_{suffix}"
    
    if not validate_character_student_id(student_id):
        raise ValueError(
            f"Generated student ID '{student_id}' failed validation. "
            f"This should not happen — please report as a bug."
        )
    
    return student_id


def get_character_lore(character: str) -> dict:
    """
    Retrieve lore information for a given character.
    
    Useful for UI display: character name, race, role, brief description.
    
    Args:
        character: Character name (lowercase, from LOTR_CHARACTERS)
    
    Returns:
        Dict with keys: name, race, role, description. 
        Returns empty dict if character not found.
    """
    lore_db = {
        "frodo": {
            "name": "Frodo Baggins",
            "race": "Hobbit",
            "role": "Ring-bearer",
            "description": "The brave hobbit who carries the One Ring to Mount Doom.",
        },
        "samwise": {
            "name": "Samwise Gamgee",
            "race": "Hobbit",
            "role": "Companion",
            "description": "Frodo's loyal friend and companion on the journey.",
        },
        "aragorn": {
            "name": "Aragorn",
            "race": "Human",
            "role": "Ranger",
            "description": "The rightful heir to the throne of Gondor.",
        },
        "legolas": {
            "name": "Legolas",
            "race": "Elf",
            "role": "Archer",
            "description": "Elven prince and master archer from Mirkwood.",
        },
        "gimli": {
            "name": "Gimli",
            "race": "Dwarf",
            "role": "Warrior",
            "description": "Dwarf warrior from the Lonely Mountain.",
        },
        "gandalf": {
            "name": "Gandalf",
            "race": "Wizard",
            "role": "Guide",
            "description": "The Grey Wizard who guides the Fellowship.",
        },
        "boromir": {
            "name": "Boromir",
            "race": "Human",
            "role": "Warrior",
            "description": "Proud warrior of Gondor, son of Denethor.",
        },
        "merry": {
            "name": "Meriadoc Brandybuck",
            "race": "Hobbit",
            "role": "Warrior",
            "description": "Courageous hobbit and loyal friend.",
        },
        "pippin": {
            "name": "Peregrin Took",
            "race": "Hobbit",
            "role": "Scout",
            "description": "Cheerful hobbit and adventurous spirit.",
        },
        "sauron": {
            "name": "Sauron",
            "race": "Maiar",
            "role": "Dark Lord",
            "description": "The Dark Lord of Mordor, creator of the One Ring.",
        },
        "saruman": {
            "name": "Saruman",
            "race": "Wizard",
            "role": "Traitor",
            "description": "The White Wizard, corrupted by power.",
        },
        "galadriel": {
            "name": "Galadriel",
            "race": "Elf",
            "role": "Queen",
            "description": "Wise Elven queen of Lothlórien.",
        },
        "elrond": {
            "name": "Elrond",
            "race": "Elf",
            "role": "Lord",
            "description": "Elven lord of Rivendell, guardian of the Vilya.",
        },
        "lorien": {
            "name": "Lothlórien",
            "race": "Realm",
            "role": "Sanctuary",
            "description": "The golden wood, sanctuary of the Elves.",
        },
        "denethor": {
            "name": "Denethor",
            "race": "Human",
            "role": "Steward",
            "description": "Steward of Gondor, father of Boromir and Faramir.",
        },
        "theoden": {
            "name": "Théoden",
            "race": "Human",
            "role": "King",
            "description": "King of Rohan, freed from Saruman's influence.",
        },
        "treebeard": {
            "name": "Treebeard",
            "race": "Ent",
            "role": "Guardian",
            "description": "Ancient Ent shepherd of the trees.",
        },
        "shelob": {
            "name": "Shelob",
            "race": "Spider",
            "role": "Guardian",
            "description": "Great spider of Moria, guardian of the mountain passes.",
        },
        "eomer": {
            "name": "Éomer",
            "race": "Human",
            "role": "Warrior",
            "description": "Brave warrior of Rohan.",
        },
        "eowyn": {
            "name": "Éowyn",
            "race": "Human",
            "role": "Warrior",
            "description": "Shield-maiden of Rohan, strong and courageous.",
        },
        "balin": {
            "name": "Balin",
            "race": "Dwarf",
            "role": "Warrior",
            "description": "Dwarf companion of Thorin, later lord of Moria.",
        },
        "dori": {
            "name": "Dori",
            "race": "Dwarf",
            "role": "Warrior",
            "description": "Dwarf of Thorin's company.",
        },
        "glorfindel": {
            "name": "Glorfindel",
            "race": "Elf",
            "role": "Warrior",
            "description": "Mighty Elven warrior of Rivendell.",
        },
        "arwen": {
            "name": "Arwen",
            "race": "Elf",
            "role": "Healer",
            "description": "Daughter of Elrond, healer and warrior.",
        },
        "celeborn": {
            "name": "Celeborn",
            "race": "Elf",
            "role": "Lord",
            "description": "Elven lord of Lothlórien, spouse of Galadriel.",
        },
        "balrog": {
            "name": "Balrog of Morgoth",
            "race": "Demon",
            "role": "Menace",
            "description": "Ancient demon of shadow and flame.",
        },
        "bilbo": {
            "name": "Bilbo Baggins",
            "race": "Hobbit",
            "role": "Adventurer",
            "description": "Frodo's uncle, finder of the One Ring.",
        },
        "smeagol": {
            "name": "Sméagol",
            "race": "Hobbit-like",
            "role": "Guide",
            "description": "Former Stoor-hobbit, corrupted by the Ring.",
        },
        "gollum": {
            "name": "Gollum",
            "race": "Creature",
            "role": "Obsessed",
            "description": "Sméagol's darker personality, obsessed with the Precious.",
        },
        "gothmog": {
            "name": "Gothmog",
            "race": "Orc",
            "role": "Commander",
            "description": "Lieutenant of Barad-dûr, commander of Mordor's forces.",
        },
        "lurtz": {
            "name": "Lurtz",
            "race": "Uruk-hai",
            "role": "Hunter",
            "description": "Uruk-hai archer, hunter of the Fellowship.",
        },
        "witch_king": {
            "name": "Witch-king of Angmar",
            "race": "Nazgûl",
            "role": "Dread Lord",
            "description": "Most powerful of the Nine, king of the dead.",
        },
        "mouth_sauron": {
            "name": "Mouth of Sauron",
            "race": "Human",
            "role": "Interpreter",
            "description": "Black Liar, voice of the Dark Lord.",
        },
        "beregond": {
            "name": "Beregond",
            "race": "Human",
            "role": "Guard",
            "description": "Guard of the Citadel, steadfast defender of Gondor.",
        },
        "shadowfax": {
            "name": "Shadowfax",
            "race": "Horse",
            "role": "Steed",
            "description": "Mightiest horse of Rohan, swift as the wind.",
        },
        "grimbold": {
            "name": "Grimbold",
            "race": "Human",
            "role": "Warrior",
            "description": "Warrior of Rohan, keeper of the Kings of Old.",
        },
    }
    
    char_lower = character.lower()
    return lore_db.get(char_lower, {})


if __name__ == "__main__":
    # Demo: generate a few student IDs
    print("Fellowship Student Identity Generator Demo")
    print("=" * 50)
    for i in range(5):
        student_id = generate_character_student_id()
        char = student_id.split("_")[0]
        lore = get_character_lore(char)
        print(f"\n{i+1}. Student ID: {student_id}")
        if lore:
            print(f"   Character: {lore.get('name')}")
            print(f"   Race: {lore.get('race')}")
            print(f"   Role: {lore.get('role')}")
            print(f"   Description: {lore.get('description')}")
        print(f"   Valid: {validate_character_student_id(student_id)}")
