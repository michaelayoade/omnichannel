"""Redis cache implementation for WhatsApp integrations to improve performance."""

import logging
from datetime import datetime

from django.conf import settings
from django.core.cache import cache

from .models import WhatsAppBusinessAccount

logger = logging.getLogger(__name__)

# Cache keys and timeouts
RATE_LIMIT_KEY_PREFIX = "whatsapp:rate_limit:"
RATE_LIMIT_TIMEOUT = 3600  # 1 hour in seconds
TEMPLATE_CACHE_KEY_PREFIX = "whatsapp:templates:"
TEMPLATE_CACHE_TIMEOUT = 86400  # 24 hours in seconds
BUSINESS_PROFILE_KEY_PREFIX = "whatsapp:business_profile:"
BUSINESS_PROFILE_TIMEOUT = 86400  # 24 hours in seconds


def get_rate_limit_cache_key(business_account_id: str, endpoint: str) -> str:
    """Generate cache key for rate limit."""
    return f"{RATE_LIMIT_KEY_PREFIX}{business_account_id}:{endpoint}"


def get_template_cache_key(business_account_id: str) -> str:
    """Generate cache key for templates."""
    return f"{TEMPLATE_CACHE_KEY_PREFIX}{business_account_id}"


def get_business_profile_cache_key(business_account_id: str) -> str:
    """Generate cache key for business profile."""
    return f"{BUSINESS_PROFILE_KEY_PREFIX}{business_account_id}"


def get_cached_rate_limit(
    business_account: WhatsAppBusinessAccount, endpoint: str,
) -> dict | None:
    """Get rate limit information from cache.

    Returns cached rate limit info or None if not in cache.
    """
    cache_key = get_rate_limit_cache_key(business_account.business_account_id, endpoint)
    rate_limit_data = cache.get(cache_key)

    if rate_limit_data:
        logger.debug(f"Rate limit cache hit for {cache_key}")
        return rate_limit_data

    logger.debug(f"Rate limit cache miss for {cache_key}")
    return None


def update_rate_limit_cache(
    business_account: WhatsAppBusinessAccount,
    endpoint: str,
    request_count: int,
    window_start: datetime,
    window_end: datetime,
    is_blocked: bool = False,
) -> None:
    """Update rate limit information in cache."""
    cache_key = get_rate_limit_cache_key(business_account.business_account_id, endpoint)

    # Convert datetime objects to ISO format strings for JSON serialization
    data = {
        "request_count": request_count,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "is_blocked": is_blocked,
    }

    # Set with timeout
    cache.set(cache_key, data, timeout=RATE_LIMIT_TIMEOUT)
    logger.debug(f"Updated rate limit cache for {cache_key}")


def invalidate_rate_limit_cache(
    business_account: WhatsAppBusinessAccount, endpoint: str,
) -> None:
    """Invalidate rate limit cache."""
    cache_key = get_rate_limit_cache_key(business_account.business_account_id, endpoint)
    cache.delete(cache_key)
    logger.debug(f"Invalidated rate limit cache for {cache_key}")


def get_cached_templates(
    business_account: WhatsAppBusinessAccount,
) -> list[dict] | None:
    """Get templates from cache."""
    if not getattr(settings, "WHATSAPP_USE_CACHE", True):
        return None

    cache_key = get_template_cache_key(business_account.business_account_id)
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.debug(f"Templates cache hit for {cache_key}")
        return cached_data

    logger.debug(f"Templates cache miss for {cache_key}")
    return None


def cache_templates(
    business_account: WhatsAppBusinessAccount, templates: list[dict],
) -> None:
    """Cache templates for future use."""
    if not getattr(settings, "WHATSAPP_USE_CACHE", True):
        return

    cache_key = get_template_cache_key(business_account.business_account_id)
    cache.set(cache_key, templates, timeout=TEMPLATE_CACHE_TIMEOUT)
    logger.debug(f"Cached {len(templates)} templates for {cache_key}")


def invalidate_templates_cache(business_account: WhatsAppBusinessAccount) -> None:
    """Invalidate templates cache when templates are modified."""
    cache_key = get_template_cache_key(business_account.business_account_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated templates cache for {cache_key}")


def get_cached_business_profile(
    business_account: WhatsAppBusinessAccount,
) -> dict | None:
    """Get business profile from cache."""
    if not getattr(settings, "WHATSAPP_USE_CACHE", True):
        return None

    cache_key = get_business_profile_cache_key(business_account.business_account_id)
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.debug(f"Business profile cache hit for {cache_key}")
        return cached_data

    logger.debug(f"Business profile cache miss for {cache_key}")
    return None


def cache_business_profile(
    business_account: WhatsAppBusinessAccount, profile_data: dict,
) -> None:
    """Cache business profile for future use."""
    if not getattr(settings, "WHATSAPP_USE_CACHE", True):
        return

    cache_key = get_business_profile_cache_key(business_account.business_account_id)
    cache.set(cache_key, profile_data, timeout=BUSINESS_PROFILE_TIMEOUT)
    logger.debug(f"Cached business profile for {cache_key}")


def invalidate_business_profile_cache(
    business_account: WhatsAppBusinessAccount,
) -> None:
    """Invalidate business profile cache when profile is updated."""
    cache_key = get_business_profile_cache_key(business_account.business_account_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated business profile cache for {cache_key}")
