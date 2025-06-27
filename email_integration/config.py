"""
Configuration settings for the email_integration app.

This module centralizes all configuration settings for the email integration app,
pulling values from environment variables with sensible defaults.
"""

import os

from django.conf import settings

# Default values - will be overridden by environment variables if set
DEFAULT_CONFIG = {
    # Email polling settings
    "POLLING_INTERVAL": 300,  # Default: 5 minutes
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 300,  # Default: 5 minutes
    "ATTACHMENT_SIZE_LIMIT": 10 * 1024 * 1024,  # Default: 10MB
    "MAX_MESSAGE_AGE_DAYS": 30,  # Default: 30 days
    "MAX_MESSAGES_PER_POLL": 100,  # Default: 100 messages per poll
    # Security settings
    "ENCRYPTION_ENABLED": True,
    "ENCRYPTION_KEY": None,  # Must be set in environment
    "ENCRYPTION_SALT": None,  # Must be set in environment
    # Connection timeouts (in seconds)
    "IMAP_TIMEOUT": 30,
    "SMTP_TIMEOUT": 30,
    "DEFAULT_TIMEOUT": 30,  # Default timeout for all connections
    # Feature flags
    "AUTO_CATEGORIZATION_ENABLED": True,
    "ATTACHMENT_SCANNING_ENABLED": True,
}


def get_config(key, default=None):
    """
    Get a configuration value from environment variables or settings with fallback.

    Args:
        key: The configuration key to look up
        default: Default value if not found

    Returns:
        The configuration value
    """
    # Special case to bridge the app's config with the main project settings.
    if key == "ENCRYPTION_KEY" and hasattr(settings, "FIELD_ENCRYPTION_KEY"):
        return settings.FIELD_ENCRYPTION_KEY

    # Check if the key exists in the environment with EMAIL_ prefix
    env_key = f"EMAIL_{key}"
    if env_key in os.environ:
        value = os.environ[env_key]

        # Try to convert value to appropriate type based on default
        if isinstance(default, bool):
            return value.lower() in ("true", "yes", "1")
        elif isinstance(default, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        return value

    # Check if the key exists in Django settings
    if hasattr(settings, env_key):
        return getattr(settings, env_key)

    # Check in default config
    if key in DEFAULT_CONFIG:
        return DEFAULT_CONFIG[key]

    # Return provided default if all else fails
    return default


# Commonly used settings exported for convenience
POLLING_INTERVAL = get_config("POLLING_INTERVAL", DEFAULT_CONFIG["POLLING_INTERVAL"])
MAX_RETRIES = get_config("MAX_RETRIES", DEFAULT_CONFIG["MAX_RETRIES"])
RETRY_DELAY = get_config("RETRY_DELAY", DEFAULT_CONFIG["RETRY_DELAY"])
MAX_ATTACHMENT_SIZE = get_config(
    "ATTACHMENT_SIZE_LIMIT", DEFAULT_CONFIG["ATTACHMENT_SIZE_LIMIT"]
)
MAX_MESSAGE_AGE_DAYS = get_config(
    "MAX_MESSAGE_AGE_DAYS", DEFAULT_CONFIG["MAX_MESSAGE_AGE_DAYS"]
)
MAX_MESSAGES_PER_POLL = get_config(
    "MAX_MESSAGES_PER_POLL", DEFAULT_CONFIG["MAX_MESSAGES_PER_POLL"]
)
DEFAULT_TIMEOUT = get_config("DEFAULT_TIMEOUT", DEFAULT_CONFIG["DEFAULT_TIMEOUT"])

# Security settings
ENCRYPTION_ENABLED = get_config(
    "ENCRYPTION_ENABLED", DEFAULT_CONFIG["ENCRYPTION_ENABLED"]
)
ENCRYPTION_KEY = get_config("ENCRYPTION_KEY", DEFAULT_CONFIG["ENCRYPTION_KEY"])
ENCRYPTION_SALT = get_config("ENCRYPTION_SALT", DEFAULT_CONFIG["ENCRYPTION_SALT"])

# Feature flags
AUTO_CATEGORIZATION_ENABLED = get_config(
    "AUTO_CATEGORIZATION_ENABLED", DEFAULT_CONFIG["AUTO_CATEGORIZATION_ENABLED"]
)
ATTACHMENT_SCANNING_ENABLED = get_config(
    "ATTACHMENT_SCANNING_ENABLED", DEFAULT_CONFIG["ATTACHMENT_SCANNING_ENABLED"]
)
