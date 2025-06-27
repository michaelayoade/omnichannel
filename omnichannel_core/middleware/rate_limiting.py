"""Rate limiting middleware to protect API endpoints from abuse."""

import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)

# Cache configuration
RATE_LIMIT_KEY_PREFIX = "rate_limit:"
RATE_LIMIT_TIMEOUT = 3600  # 1 hour in seconds


def get_client_ip(request: HttpRequest) -> str:
    """Get the client IP address from request.
    Uses X-Forwarded-For header if available and trusted.
    """
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Use first forwarded IP in the chain
            return x_forwarded_for.split(",")[0].strip()
    # Otherwise use the direct client IP
    return request.META.get("REMOTE_ADDR", "unknown")


def get_rate_limit_cache_key(
    view_name: str, ip_address: str, path: str | None = None, username: str | None = None,
) -> str:
    """Generate cache key for rate limit."""
    identifiers = [view_name, ip_address]
    if path:
        identifiers.append(path)
    if username:
        identifiers.append(username)

    combined = ":".join(identifiers)
    # Use hash for potentially long keys
    if len(combined) > 200:
        combined = hashlib.sha256(combined.encode()).hexdigest()

    return f"{RATE_LIMIT_KEY_PREFIX}{combined}"


class RateLimitMiddleware:
    """Middleware for rate limiting API requests.
    Configurable per-view using settings.RATE_LIMITS.

    Rate limits are applied based on:
    - IP address
    - Path parameters (optional)
    - Authenticated username (optional)

    Example settings:
    RATE_LIMITS = {
        'api_view_name': {
            'rate': '10/minute',  # or '100/hour', '1000/day'
            'by_user': True,      # Include username in rate limit key
            'by_path': True,      # Include path in rate limit key
            'block_time': 3600,   # Time to block after limit reached (seconds)
        }
    }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = getattr(settings, "RATE_LIMITS", {})
        self.enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)

        # Parse rate limit configurations
        self.parsed_limits = {}
        for view_name, config in self.rate_limits.items():
            rate = config.get("rate", "60/minute")
            count, period = rate.split("/")
            seconds = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }.get(period.strip().lower(), 60)

            self.parsed_limits[view_name] = {
                "count": int(count),
                "period": seconds,
                "by_user": config.get("by_user", False),
                "by_path": config.get("by_path", False),
                "block_time": config.get("block_time", 3600),
            }

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        view_name = getattr(request.resolver_match, "view_name", None)
        if not view_name or view_name not in self.parsed_limits:
            return self.get_response(request)

        limit_config = self.parsed_limits[view_name]

        # Gather identifiers for this request
        ip_address = get_client_ip(request)
        path = request.path if limit_config["by_path"] else None
        username = request.user.username if limit_config["by_user"] and request.user.is_authenticated else None

        # Check if this request should be rate limited
        exceeded, remaining, reset_time = self.check_rate_limit(
            view_name,
            ip_address,
            limit_config["count"],
            limit_config["period"],
            path,
            username,
        )

        # Add rate limit headers to response
        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(limit_config["count"])
        response["X-RateLimit-Remaining"] = str(remaining)
        response["X-RateLimit-Reset"] = str(reset_time)

        if exceeded:
            logger.warning(
                f"Rate limit exceeded for {view_name} by {ip_address}"
                f"{f' (user: {username})' if username else ''}",
            )
            return JsonResponse(
                {"error": "Rate limit exceeded", "retry_after": reset_time},
                status=429,
            )

        return response

    def check_rate_limit(
        self,
        view_name: str,
        ip_address: str,
        limit: int,
        period: int,
        path: str | None = None,
        username: str | None = None,
    ) -> tuple[bool, int, int]:
        """Check if request exceeds rate limit.

        Returns
        -------
            Tuple of (exceeded, remaining, reset_time)
            exceeded: True if rate limit is exceeded
            remaining: Number of requests remaining in this period
            reset_time: Seconds until the current period ends

        """
        now = int(time.time())
        cache_key = get_rate_limit_cache_key(view_name, ip_address, path, username)

        # Get current count from cache
        record = cache.get(cache_key)

        if not record:
            # New rate limit record
            record = {
                "count": 1,
                "start_time": now,
                "end_time": now + period,
                "blocked_until": None,
            }
            remaining = limit - 1
            reset_time = period
        else:
            # Check for block
            if record["blocked_until"] and now < record["blocked_until"]:
                return True, 0, record["blocked_until"] - now

            # Current period expired
            if now > record["end_time"]:
                # Start a new period
                record = {
                    "count": 1,
                    "start_time": now,
                    "end_time": now + period,
                    "blocked_until": None,
                }
                remaining = limit - 1
                reset_time = period
            else:
                # Within current period
                record["count"] += 1
                remaining = max(0, limit - record["count"])
                reset_time = record["end_time"] - now

                # Check if limit exceeded
                if record["count"] > limit:
                    # Set blocked flag with the configured block time
                    block_time = self.rate_limits[view_name].get("block_time", 3600)
                    record["blocked_until"] = now + block_time
                    return True, 0, block_time

        # Update record in cache
        cache.set(cache_key, record, timeout=period * 2)  # 2x period for safety
        return False, remaining, reset_time
