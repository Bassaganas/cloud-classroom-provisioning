"""
Unit tests for generate_student_identity module.

Tests character generation, validation, and LOTR character pool functionality.
"""

import pytest
import re
from generate_student_identity import (
    generate_short_uuid,
    generate_character_student_id,
    validate_character_student_id,
    get_character_lore,
    LOTR_CHARACTERS,
)


class TestGenerateShortUuid:
    """Tests for generate_short_uuid function."""
    
    def test_default_length(self):
        """Default suffix should be 4 characters."""
        uuid_str = generate_short_uuid()
        assert len(uuid_str) == 4
        assert uuid_str.islower()
        assert all(c in "0123456789abcdef" for c in uuid_str)
    
    def test_custom_length(self):
        """Should support custom suffix lengths."""
        for length in [3, 5, 6, 8]:
            uuid_str = generate_short_uuid(length)
            assert len(uuid_str) == length
    
    def test_randomness(self):
        """Multiple calls should produce different suffixes."""
        uuids = [generate_short_uuid() for _ in range(10)]
        # With 4 hex chars (65536 combinations), collision probability is very low
        assert len(set(uuids)) == len(uuids), "Suffixes should be unique"
    
    def test_lowercase_only(self):
        """Generated UUIDs should be lowercase hex."""
        for _ in range(20):
            uuid_str = generate_short_uuid()
            assert uuid_str == uuid_str.lower()


class TestValidateCharacterStudentId:
    """Tests for validate_character_student_id regex validation."""
    
    def test_valid_formats(self):
        """Valid student IDs should pass validation."""
        valid_ids = [
            "legolas_xy37",
            "frodo_abc1",
            "gandalf_zzzz",
            "aragorn_0000",
            "gimli_ffff",
            "samwise_9999",
        ]
        for student_id in valid_ids:
            assert validate_character_student_id(student_id), f"Should be valid: {student_id}"
    
    def test_invalid_character_names(self):
        """IDs with hyphens/underscores in character name should fail."""
        invalid_ids = [
            "witch_king_xy37",  # Underscore in character name
            "mouth-sauron_xy37",  # Hyphen in character name
            "Legolas_xy37",  # Uppercase character name
            "student-xyz_xy37",  # Old format with hyphen
        ]
        for student_id in invalid_ids:
            assert not validate_character_student_id(student_id), f"Should be invalid: {student_id}"
    
    def test_invalid_suffix_length(self):
        """Suffixes must be 3-4 characters."""
        invalid_ids = [
            "legolas_ab",  # Too short (2 chars)
            "legolas_abcde",  # Too long (5 chars)
            "legolas_",  # Empty suffix
            "legolas",  # Missing suffix separator
        ]
        for student_id in invalid_ids:
            assert not validate_character_student_id(student_id), f"Should be invalid: {student_id}"
    
    def test_invalid_suffix_characters(self):
        """Suffixes must be hex (lowercase only)."""
        invalid_ids = [
            "legolas_XY37",  # Uppercase
            "legolas_AB37",  # Uppercase hex
            "legolas_xy!7",  # Special char
            "legolas_xy-7",  # Hyphen
        ]
        for student_id in invalid_ids:
            assert not validate_character_student_id(student_id), f"Should be invalid: {student_id}"


class TestGenerateCharacterStudentId:
    """Tests for generate_character_student_id function."""
    
    def test_random_generation(self):
        """Should generate valid student IDs with random character."""
        for _ in range(20):
            student_id = generate_character_student_id()
            assert validate_character_student_id(student_id)
    
    def test_specific_character(self):
        """Should generate ID with specified character."""
        for char in ["frodo", "legolas", "gandalf"]:
            student_id = generate_character_student_id(character=char)
            assert student_id.startswith(f"{char}_")
            assert validate_character_student_id(student_id)
    
    def test_character_case_insensitive(self):
        """Should accept character names in any case."""
        for char in ["Frodo", "LEGOLAS", "gAnDaLf"]:
            student_id = generate_character_student_id(character=char)
            assert validate_character_student_id(student_id)
    
    def test_invalid_character_raises(self):
        """Should raise ValueError for non-existent characters."""
        with pytest.raises(ValueError) as exc_info:
            generate_character_student_id(character="gandalf_the_grey")
        assert "not in LOTR pool" in str(exc_info.value)
    
    def test_custom_suffix_length(self):
        """Should support custom suffix lengths."""
        student_id_3 = generate_character_student_id(suffix_length=3)
        student_id_6 = generate_character_student_id(suffix_length=6)
        
        suffix_3 = student_id_3.split("_")[1]
        suffix_6 = student_id_6.split("_")[1]
        
        assert len(suffix_3) == 3
        assert len(suffix_6) == 6
    
    def test_uniqueness(self):
        """Multiple generations should produce unique IDs."""
        student_ids = [generate_character_student_id() for _ in range(20)]
        assert len(set(student_ids)) == len(student_ids)
    
    def test_format_consistency(self):
        """All generated IDs should follow the format exactly."""
        pattern = re.compile(r"^[a-z]+_[a-z0-9]{3,4}$")
        for _ in range(30):
            student_id = generate_character_student_id()
            assert pattern.match(student_id), f"Format mismatch: {student_id}"


class TestCharacterPool:
    """Tests for LOTR character pool."""
    
    def test_character_pool_not_empty(self):
        """Character pool should have characters."""
        assert len(LOTR_CHARACTERS) > 0
    
    def test_all_characters_lowercase(self):
        """All characters in pool should be lowercase."""
        for char in LOTR_CHARACTERS:
            assert char == char.lower()
    
    def test_minimum_pool_size(self):
        """Pool should have at least 15 characters (recommended minimum)."""
        assert len(LOTR_CHARACTERS) >= 15
    
    def test_main_fellowship_present(self):
        """Core Fellowship members should be in the pool."""
        required = ["frodo", "samwise", "aragorn", "legolas", "gimli", "gandalf"]
        for char in required:
            assert char in LOTR_CHARACTERS, f"Missing core character: {char}"


class TestGetCharacterLore:
    """Tests for get_character_lore function."""
    
    def test_lore_for_main_characters(self):
        """Should return lore for main Fellowship members."""
        for char in ["frodo", "legolas", "gandalf"]:
            lore = get_character_lore(char)
            assert "name" in lore
            assert "race" in lore
            assert "role" in lore
            assert "description" in lore
            assert len(lore["name"]) > 0
            assert len(lore["description"]) > 0
    
    def test_lore_case_insensitive(self):
        """Should accept character names in any case."""
        lore_lower = get_character_lore("frodo")
        lore_upper = get_character_lore("FRODO")
        lore_mixed = get_character_lore("FrOdO")
        
        assert lore_lower == lore_upper == lore_mixed
        assert lore_lower["name"] == "Frodo Baggins"
    
    def test_unknown_character_returns_empty(self):
        """Should return empty dict for unknown characters."""
        lore = get_character_lore("balrog_of_morgoth")
        assert lore == {}
    
    def test_lore_uniqueness(self):
        """Different characters should have different names."""
        lores = [get_character_lore(char) for char in ["frodo", "legolas", "gandalf", "gimli"]]
        names = [l.get("name") for l in lores if l]
        assert len(set(names)) == len(names), "Characters should have unique names"


class TestGroovyInjectionSafety:
    """Tests to verify Jenkins Groovy injection safety."""
    
    def test_no_groovy_special_chars_in_generated_ids(self):
        """Generated IDs should not contain Groovy special characters."""
        groovy_dangerous = ['$', '{', '}', ';', '.', '"', "'", '`']
        
        for _ in range(50):
            student_id = generate_character_student_id()
            for char in groovy_dangerous:
                assert char not in student_id, f"Dangerous char '{char}' in {student_id}"
    
    def test_character_names_groovy_safe(self):
        """All character names should be safe for Groovy substitution."""
        regex_safe = re.compile(r"^[a-z]+$")
        
        for char in LOTR_CHARACTERS:
            assert regex_safe.match(char), f"Character '{char}' not Groovy-safe"


class TestDocumentation:
    """Tests to ensure generated identifiers self-document."""
    
    def test_identifier_is_readable(self):
        """Generated IDs should be human-readable."""
        student_id = generate_character_student_id()
        char, suffix = student_id.split("_")
        
        # Character part should be recognizable
        assert char in LOTR_CHARACTERS
        # Suffix should be short and random-looking
        assert 3 <= len(suffix) <= 4
    
    def test_can_extract_character_from_id(self):
        """Character should be easily extractable from ID."""
        for char in ["frodo", "legolas", "gandalf"]:
            student_id = generate_character_student_id(character=char)
            extracted_char = student_id.split("_")[0]
            assert extracted_char == char


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
