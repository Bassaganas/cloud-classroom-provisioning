"""Configuration management for bargaining system via AWS Parameter Store."""
import json
import logging
from typing import Any, Dict, Optional
from functools import lru_cache
import os

logger = logging.getLogger(__name__)


class BargainingConfig:
    """
    Load and manage bargaining configuration.
    
    Configuration can come from:
    1. AWS Parameter Store (for runtime updates)
    2. Environment variables (for local dev)
    3. Default values (hardcoded)
    
    For now, uses environment variables. AWS Parameter Store integration
    can be added later.
    """

    # Default configuration values
    DEFAULT_CONFIG = {
        "flattery_bonus_percent": 0.05,  # 5% better offer when flattered
        "max_negotiation_rounds": {
            "frodo": 6,
            "sam": 5,
            "gandalf": 7,
        },
        "mood_change_probabilities": {
            "boredom_on_low_offer": 0.10,  # 10% chance to increase boredom
            "lucky_drop_chance": 0.10,      # 10% chance of sudden price drop
        },
        "logging_enabled": True,
        "log_retention_days": 30,
        "flattery_only_once_per_negotiation": True,
    }

    _config_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def load_config(cls, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load configuration from AWS Parameter Store or environment.
        
        Args:
            force_reload: If True, bypass cache and reload from source
            
        Returns:
            Configuration dictionary
        """
        if cls._config_cache and not force_reload:
            return cls._config_cache

        config = cls.DEFAULT_CONFIG.copy()
        
        # Try to load from AWS Parameter Store
        aws_config = cls._load_from_aws_parameter_store()
        if aws_config:
            config.update(aws_config)
            logger.info("✓ Loaded bargaining config from AWS Parameter Store")
        else:
            # Fall back to environment variables
            env_config = cls._load_from_environment()
            if env_config:
                config.update(env_config)
                logger.info("✓ Loaded bargaining config from environment variables")
            else:
                logger.info("✓ Using default bargaining configuration")
        
        cls._config_cache = config
        return config

    @classmethod
    def _load_from_aws_parameter_store(cls) -> Optional[Dict[str, Any]]:
        """Load configuration from AWS Systems Manager Parameter Store."""
        try:
            import boto3
            ssm_client = boto3.client("ssm")
            
            param_name = os.getenv("BARGAINING_CONFIG_PARAM", "/fellowship/bargaining/config")
            
            try:
                response = ssm_client.get_parameter(
                    Name=param_name,
                    WithDecryption=False
                )
                config_str = response["Parameter"]["Value"]
                config = json.loads(config_str)
                return config
            except ssm_client.exceptions.ParameterNotFound:
                logger.debug(f"Parameter {param_name} not found in Parameter Store")
                return None
        except (ImportError, Exception) as e:
            logger.debug(f"Could not load from AWS Parameter Store: {type(e).__name__}")
            return None

    @classmethod
    def _load_from_environment(cls) -> Optional[Dict[str, Any]]:
        """Load configuration from environment variables."""
        config = {}
        
        # Try to load BARGAINING_CONFIG_JSON env var
        config_json = os.getenv("BARGAINING_CONFIG_JSON")
        if config_json:
            try:
                env_config = json.loads(config_json)
                return env_config
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in BARGAINING_CONFIG_JSON env var")
        
        return None if not config else config

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key path (dot-notation supported).
        
        Example: config.get("mood_change_probabilities.lucky_drop_chance")
        """
        config = cls.load_config()
        
        if "." in key:
            parts = key.split(".")
            value = config
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return default
            return value if value is not None else default
        
        return config.get(key, default)

    @classmethod
    def get_character_config(cls, character: str) -> Dict[str, Any]:
        """Get configuration for a specific character."""
        config = cls.load_config()
        
        # Return character-specific config if it exists
        if "character_configs" in config and character in config["character_configs"]:
            return config["character_configs"][character]
        
        # Fall back to defaults
        return {
            "max_rounds": config["max_negotiation_rounds"].get(
                character, config["max_negotiation_rounds"]["gandalf"]
            ),
            "flattery_bonus": config["flattery_bonus_percent"],
        }

    @classmethod
    def clear_cache(cls) -> None:
        """Clear configuration cache (useful for testing)."""
        cls._config_cache = None
