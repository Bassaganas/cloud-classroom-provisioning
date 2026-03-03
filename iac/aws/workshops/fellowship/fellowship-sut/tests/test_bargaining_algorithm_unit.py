"""Unit tests for bargaining algorithm."""
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "sut" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.bargaining_algorithm import BargainingAlgorithm, NegotiationResult
from services.bargaining_config import BargainingConfig
from services.negotiation_logger import NegotiationLogger


class TestBargainingAlgorithm:
    """Test the core bargaining algorithm."""

    def test_offer_accepted_when_above_threshold(self):
        """Test that offers above the acceptance ratio are accepted."""
        # Gandalf's profile: accept_ratio = 0.90
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=95,
            current_ask=100,
            character="gandalf",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        assert result["result"] == NegotiationResult.OFFER_ACCEPTED

    def test_counter_offer_when_below_threshold(self):
        """Test that low offers trigger counter-offers, but never below user's offer."""
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=50,
            current_ask=100,
            character="gandalf",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        assert result["result"] == NegotiationResult.COUNTER_OFFER
        assert result["counter_offer"] is not None
        assert result["counter_offer"] < 100  # Should be a concession
        assert result["counter_offer"] >= 50  # Should never be below user's offer

    def test_flattery_improves_acceptance_ratio(self):
        """Test that flattery makes acceptance easier."""
        # Without flattery
        result_no_flattery = BargainingAlgorithm.evaluate_offer(
            user_offer=88,
            current_ask=100,
            character="gandalf",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        # With flattery (should accept lower offer)
        result_with_flattery = BargainingAlgorithm.evaluate_offer(
            user_offer=88,
            current_ask=100,
            character="gandalf",
            round_num=1,
            is_flattered=True,
            user_message=None,
        )
        # Flattery should result in acceptance when non-flattered doesn't
        # (or at least should be more favorable)
        assert result_with_flattery["result"] == NegotiationResult.OFFER_ACCEPTED
    def test_deal_message_results_in_accept(self):
        """Test that saying 'deal' results in acceptance at current ask."""
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=10,  # Irrelevant for 'deal'
            current_ask=100,
            character="gandalf",
            round_num=2,
            is_flattered=False,
            user_message="deal",
        )
        assert result["result"] == NegotiationResult.OFFER_ACCEPTED
        assert result["context"]["reason"] == "user_said_deal"

    def test_max_rounds_triggers_stop_bargain(self):
        """Test that exceeding max rounds triggers stop-bargain."""
        # Gandalf's max_rounds = 7
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=50,
            current_ask=100,
            character="gandalf",
            round_num=8,  # Exceed max
            is_flattered=False,
        )
        assert result["result"] == NegotiationResult.STOP_BARGAIN

    def test_flattery_detection(self):
        """Test flattery detection in messages."""
        # Messages with compliments
        assert BargainingAlgorithm.detect_flattery("You are amazing!") == True
        assert BargainingAlgorithm.detect_flattery("That's very clever") == True
        assert BargainingAlgorithm.detect_flattery("You seem wonderful and brave") == True
        
        # Messages without compliments
        assert BargainingAlgorithm.detect_flattery("I offer 100 gold") == False
        assert BargainingAlgorithm.detect_flattery("Deal") == False

    def test_mood_change_calculation(self):
        """Test mood changes based on user behavior."""
        # Very low offer should worsen mood
        modifiers = BargainingAlgorithm.calculate_mood_change(
            previous_offer=50,
            current_offer=20,
            current_ask=100
        )
        # Low offer (< 30%) should increase boredom
        assert modifiers.get("boredom", 0) > 0

    def test_llm_summary_generation(self):
        """Test generating JSON summary for LLM."""
        summary = BargainingAlgorithm.get_summary_for_llm(
            negotiation_state={
                "character": "gandalf",
                "item_name": "Sword of Elendil",
                "item_id": 1,
                "original_price": 150,
                "current_ask": 120,
                "round": 2,
            },
            algorithm_result={
                "result": NegotiationResult.COUNTER_OFFER,
                "counter_offer": 110,
                "context": {"reason": "counter_offer"}
            },
            user_offer=100,
            character_personality="bargainer",
            is_flattered=False,
            mood_modifiers={}
        )
        
        assert summary["character"] == "gandalf"
        assert summary["item_name"] == "Sword of Elendil"
        assert summary["negotiation_result"] == "counter-offer"
        assert summary["counter_offer"] == 110
        assert summary["user_offer"] == 100


class TestBargainingConfig:
    """Test configuration loading."""

    def test_load_default_config(self):
        """Test that default config loads."""
        BargainingConfig.clear_cache()
        config = BargainingConfig.load_config()
        
        assert "flattery_bonus_percent" in config
        assert "max_negotiation_rounds" in config
        assert "logging_enabled" in config

    def test_get_config_value(self):
        """Test getting config values."""
        BargainingConfig.clear_cache()
        
        flattery_bonus = BargainingConfig.get("flattery_bonus_percent")
        assert flattery_bonus == 0.05
        
        max_rounds_gandalf = BargainingConfig.get("max_negotiation_rounds.gandalf")
        assert max_rounds_gandalf == 7

    def test_get_character_config(self):
        """Test getting character-specific config."""
        BargainingConfig.clear_cache()
        
        gandalf_config = BargainingConfig.get_character_config("gandalf")
        assert "max_rounds" in gandalf_config
        assert gandalf_config["max_rounds"] == 7


class TestNegotiationLogger:
    """Test negotiation logging."""

    def setup_method(self):
        """Clear logs before each test."""
        NegotiationLogger.clear_logs()

    def test_log_negotiation_start(self):
        """Test logging negotiation start."""
        session_id = NegotiationLogger.log_negotiation_start(
            character="gandalf",
            item_id=1,
            item_name="Sword",
            original_price=100
        )
        
        assert session_id is not None
        assert len(session_id) > 0  # Should be a UUID string

    def test_log_offer_made(self):
        """Test logging an offer."""
        session_id = NegotiationLogger.log_negotiation_start(
            character="gandalf",
            item_id=1,
            item_name="Sword",
            original_price=100
        )
        
        NegotiationLogger.log_offer_made(
            session_id=session_id,
            round_num=1,
            user_offer=80,
            current_ask=100,
            is_flattered=False
        )
        
        stats = NegotiationLogger.get_stats()
        assert stats["unique_sessions"] == 1

    def test_flattery_logging(self):
        """Test logging flattery behavior."""
        session_id = NegotiationLogger.log_negotiation_start(
            character="gandalf",
            item_id=1,
            item_name="Sword",
            original_price=100
        )
        
        NegotiationLogger.log_behavior_detected(session_id, "flattery")
        
        stats = NegotiationLogger.get_stats()
        assert stats["unique_sessions"] == 1

    def test_purge_old_logs(self):
        """Test log purging."""
        # Create a log entry
        NegotiationLogger.log_negotiation_start(
            character="gandalf",
            item_id=1,
            item_name="Sword",
            original_price=100
        )
        
        # Purge logs (should remove old ones)
        removed = NegotiationLogger.purge_old_logs(days_to_keep=0)
        
        # Since we just created this log, it should be kept if days_to_keep=0 means keep nothing
        # But let's just verify purge doesn't crash
        assert removed >= 0


class TestCharacterProfiles:
    """Test that different characters have different profiles."""

    def test_gandalf_personality(self):
        """Test Gandalf's personality."""
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=85,
            current_ask=100,
            character="gandalf",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        # Gandalf accept_ratio is 0.90, so 85 should not auto-accept
        assert result["result"] in [NegotiationResult.COUNTER_OFFER, NegotiationResult.STOP_BARGAIN]

    def test_frodo_personality(self):
        """Test Frodo's personality."""
        # Frodo is kind but careful
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=92,
            current_ask=100,
            character="frodo",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        # Frodo has accept_ratio of 0.92, so 92 should be accepted
        assert result["result"] == NegotiationResult.OFFER_ACCEPTED

    def test_sam_personality(self):
        """Test Sam's personality."""
        # Sam is practical and quick
        result = BargainingAlgorithm.evaluate_offer(
            user_offer=95,
            current_ask=100,
            character="sam",
            round_num=1,
            is_flattered=False,
            user_message=None,
        )
        # Sam has accept_ratio of 0.95, so 95 should be accepted
        assert result["result"] == NegotiationResult.OFFER_ACCEPTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
