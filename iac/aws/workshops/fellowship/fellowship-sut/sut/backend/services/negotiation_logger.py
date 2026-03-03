"""Logging service for bargaining negotiations (anonymized)."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import hashlib
import uuid

logger = logging.getLogger(__name__)


class NegotiationLogger:
    """
    Log negotiation outcomes and user behaviors for analytics/debugging.
    
    All logs are anonymized - no user identifiers are stored.
    Each negotiation gets a unique session ID for tracking.
    """

    # In-memory store for simplicity. In production, use a database or CloudWatch Logs.
    _negotiation_logs: List[Dict[str, Any]] = []

    @classmethod
    def log_negotiation_start(
        cls,
        character: str,
        item_id: int,
        item_name: str,
        original_price: int,
    ) -> str:
        """
        Log the start of a negotiation.
        
        Returns:
            session_id: Unique identifier for this negotiation session
        """
        session_id = str(uuid.uuid4())
        
        log_entry = {
            "event_type": "negotiation_start",
            "session_id": session_id,
            "character": character,
            "item_id": item_id,
            "item_name": item_name,
            "original_price": original_price,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"Negotiation started: {session_id} for {character} - {item_name}")
        
        return session_id

    @classmethod
    def log_offer_made(
        cls,
        session_id: str,
        round_num: int,
        user_offer: int,
        current_ask: int,
        is_flattered: bool = False,
    ) -> None:
        """Log when the user makes an offer."""
        log_entry = {
            "event_type": "offer_made",
            "session_id": session_id,
            "round": round_num,
            "user_offer": user_offer,
            "current_ask": current_ask,
            "offer_ratio": round(user_offer / current_ask, 3) if current_ask > 0 else 0,
            "is_flattered": is_flattered,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"Offer made in {session_id}: {user_offer} (ask was {current_ask})")

    @classmethod
    def log_algorithm_result(
        cls,
        session_id: str,
        result_type: str,
        context: Dict[str, Any],
    ) -> None:
        """Log the algorithm's decision."""
        log_entry = {
            "event_type": "algorithm_result",
            "session_id": session_id,
            "result": result_type,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"Algorithm result for {session_id}: {result_type}")

    @classmethod
    def log_negotiation_end(
        cls,
        session_id: str,
        final_status: str,  # "accepted", "rejected", "bored", "stopped"
        final_price: Optional[int] = None,
        rounds_taken: int = 0,
    ) -> None:
        """Log the end of a negotiation."""
        log_entry = {
            "event_type": "negotiation_end",
            "session_id": session_id,
            "final_status": final_status,
            "final_price": final_price,
            "rounds_taken": rounds_taken,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"Negotiation ended: {session_id} - {final_status} after {rounds_taken} rounds")

    @classmethod
    def log_behavior_detected(
        cls,
        session_id: str,
        behavior_type: str,  # "flattery", "persistence", "politeness", etc.
    ) -> None:
        """Log when a user behavior is detected."""
        log_entry = {
            "event_type": "behavior_detected",
            "session_id": session_id,
            "behavior": behavior_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"Behavior detected in {session_id}: {behavior_type}")

    @classmethod
    def log_llm_interaction(
        cls,
        session_id: str,
        llm_input_summary: Dict[str, Any],
        llm_output: str,
    ) -> None:
        """Log LLM interaction for debugging."""
        log_entry = {
            "event_type": "llm_interaction",
            "session_id": session_id,
            "llm_prompt_fields": list(llm_input_summary.keys()),
            "llm_output_length": len(llm_output),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        cls._negotiation_logs.append(log_entry)
        logger.debug(f"LLM interaction in {session_id}: generated {len(llm_output)} char response")

    @classmethod
    def purge_old_logs(cls, days_to_keep: int = 30) -> int:
        """
        Remove logs older than specified days.
        
        Returns:
            Number of logs removed
        """
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()
        initial_count = len(cls._negotiation_logs)
        
        cls._negotiation_logs = [
            log for log in cls._negotiation_logs
            if log.get("timestamp", "") > cutoff_date
        ]
        
        removed_count = initial_count - len(cls._negotiation_logs)
        if removed_count > 0:
            logger.info(f"Purged {removed_count} negotiation logs older than {days_to_keep} days")
        
        return removed_count

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get aggregated statistics from logs (for monitoring)."""
        if not cls._negotiation_logs:
            return {
                "total_logs": 0,
                "negotiation_sessions": 0,
            }
        
        # Count unique sessions
        sessions = set()
        accepted_count = 0
        rejected_count = 0
        flattery_count = 0
        
        for log in cls._negotiation_logs:
            if log.get("session_id"):
                sessions.add(log["session_id"])
            if log.get("event_type") == "negotiation_end":
                if log.get("final_status") == "accepted":
                    accepted_count += 1
                elif log.get("final_status") == "rejected":
                    rejected_count += 1
            if log.get("is_flattered"):
                flattery_count += 1
        
        return {
            "total_logs": len(cls._negotiation_logs),
            "unique_sessions": len(sessions),
            "successful_negotiations": accepted_count,
            "failed_negotiations": rejected_count,
            "flattery_attempts": flattery_count,
        }

    @classmethod
    def clear_logs(cls) -> None:
        """Clear all logs (for testing)."""
        cls._negotiation_logs = []
