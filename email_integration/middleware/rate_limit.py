"""Rate limiting middleware for the email integration app.

This module provides rate limiting protection for the application's REST APIs.
It protects against brute-force attacks and resource abuse by limiting request
frequency from the same source.
"""

import threading
import time
from collections import defaultdict

from django.http import HttpResponse

from omnichannel_core.utils.logging import ContextLogger

from ..config import get_config

logger = ContextLogger(__name__)


class RateLimitMiddleware:
    """Middleware that applies rate limiting to API requests.

    Uses an in-memory cache that tracks requests by IP address or user ID
    and rejects requests that exceed configured thresholds.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.request_cache = defaultdict(list)
        self.lock = threading.RLock()  # Thread-safe cache access

        # Rate limit configuration
        self.time_window = get_config("RATE_LIMIT_WINDOW", 60)  # seconds
        self.max_requests = get_config(
            "RATE_LIMIT_MAX_REQUESTS", 30,
        )  # requests per window
        self.enabled = get_config("RATE_LIMIT_ENABLED", True)

        # Exempt paths
        self.exempt_paths = [
            "/admin/",
            "/static/",
            "/media/",
            "/health/",
        ]

    def __call__(self, request):
        # Skip rate limiting for exempt paths
        path = request.path
        if not self.enabled or self._is_path_exempt(path):
            return self.get_response(request)

        # Get identifier for the requester (IP or user ID)
        request_id = self._get_requester_id(request)

        # Check if the request is over the rate limit
        if self._is_rate_limited(request_id):
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "ip": self._get_client_ip(request),
                    "path": request.path,
                    "method": request.method,
                    "user_id": getattr(request.user, "id", None),
                    "request_id": getattr(request, "request_id", None),
                },
            )
            return HttpResponse(
                "Too many requests. Please try again later.",
                status=429,
                content_type="text/plain",
            )

        return self.get_response(request)

    def _is_path_exempt(self, path):
        """Check if a path is exempt from rate limiting."""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    def _get_requester_id(self, request):
        """Get a unique identifier for the requester.

        Uses user ID for authenticated users, IP address otherwise.
        """
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"
        return f"ip:{self._get_client_ip(request)}"

    def _is_rate_limited(self, request_id):
        """Check if a requester has exceeded their rate limit.

        Updates the request cache with the current request timestamp.
        Removes old requests outside the time window.
        """
        now = time.time()

        with self.lock:
            # Clean up old requests
            self.request_cache[request_id] = [
                timestamp
                for timestamp in self.request_cache[request_id]
                if now - timestamp < self.time_window
            ]

            # Add current request
            self.request_cache[request_id].append(now)

            # Check if over the limit
            return len(self.request_cache[request_id]) > self.max_requests

    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
