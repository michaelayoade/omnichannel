"""
Account lockout middleware to protect against brute force authentication attacks.

This module implements a middleware component that tracks failed login attempts
and temporarily locks accounts after repeated failures.
"""

import re
from typing import Any, Callable, Dict, Optional

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger

from ..config import get_config

logger = ContextLogger(__name__)

# Cache keys are prefixed to avoid collisions
CACHE_PREFIX = "auth_attempt:"
LOCKOUT_PREFIX = "account_lock:"


class AccountLockoutMiddleware:
    """
    Middleware that implements account lockout after repeated failed authentications.

    Tracks failed login attempts by username and/or IP address, and
    temporarily locks accounts after a configurable threshold is reached.
    """

    def __init__(self, get_response: Callable):
        """
        Initialize middleware with response handler.

        Args:
            get_response: Callable that takes a request and returns a response
        """
        self.get_response = get_response

        # Configurable settings
        self.enabled = get_config("ACCOUNT_LOCKOUT_ENABLED", True)
        self.max_attempts = get_config("ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 5)
        self.lockout_duration = get_config("ACCOUNT_LOCKOUT_DURATION", 30)  # minutes
        self.reset_after = get_config("ACCOUNT_LOCKOUT_RESET_AFTER", 60)  # minutes

        # Login paths to monitor (can be configured in settings)
        self.login_paths = get_config(
            "ACCOUNT_LOCKOUT_PATHS",
            [
                "/api/auth/login/",
                "/admin/login/",
                "/accounts/login/",
                "/api/token/",  # JWT token endpoint
            ],
        )

        # Regular expression to match username or email in request body
        self.username_regex = re.compile(
            r'["\']?(username|email)["\']?\s*:\s*["\']([^"\']+)["\']?'
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and apply account lockout logic if applicable.

        Args:
            request: The incoming HTTP request

        Returns:
            HTTP response
        """
        if not self.enabled:
            return self.get_response(request)

        # Check if this is a login attempt
        if request.method == "POST" and self._is_login_path(request.path):
            # Extract identity (username/email) from request
            identity = self._extract_identity(request)

            if identity:
                # Check if account is locked
                if self._is_account_locked(identity, request):
                    logger.warning(
                        "Blocked login attempt for locked account",
                        extra={
                            "ip_address": self._get_client_ip(request),
                            "path": request.path,
                            "identity": identity,
                        },
                    )

                    # Return a JSON response for API endpoints
                    if any(path in request.path for path in ("/api/", "/token/")):
                        return JsonResponse(
                            {
                                "error": "Too many failed login attempts. Account temporarily locked.",
                                "detail": f"Please try again in {self.lockout_duration} minutes.",
                            },
                            status=403,
                        )
                    else:
                        # For non-API endpoints, let the view handle it normally
                        # but add a flag to the request
                        request.account_locked = True

            # Mark the login attempt for tracking
            # We do this regardless of lockout status to track attempts during lockout
            self._mark_login_attempt(identity, request)

        response = self.get_response(request)

        # Check response for login failure (status 401, 403 for REST APIs)
        if (
            request.method == "POST"
            and self._is_login_path(request.path)
            and response.status_code in (401, 403)
        ):
            identity = self._extract_identity(request)

            if identity:
                # Increment failed attempts counter
                self._register_failed_attempt(identity, request)

        return response

    def _is_login_path(self, path: str) -> bool:
        """
        Check if the request path is a login endpoint.

        Args:
            path: The request path

        Returns:
            True if this is a login path, False otherwise
        """
        return any(login_path in path for login_path in self.login_paths)

    def _extract_identity(self, request: HttpRequest) -> Optional[str]:
        """
        Extract username or email from request.

        Args:
            request: The HTTP request

        Returns:
            Username/email string or None if not found
        """
        # First check form data
        identity = request.POST.get("username") or request.POST.get("email")

        # If not found, try to extract from JSON data
        if not identity and hasattr(request, "body"):
            try:
                # Parse request body as text and look for username/email
                body_str = request.body.decode("utf-8")
                match = self.username_regex.search(body_str)
                if match:
                    identity = match.group(2)
            except (UnicodeDecodeError, AttributeError):
                pass

        return identity.lower() if identity else None

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get the client IP address from request.

        Args:
            request: The HTTP request

        Returns:
            IP address string
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # X-Forwarded-For can be a comma-separated list of IPs.
            # The client's IP is the first one.
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")
        return ip

    def _get_cache_key(self, identity: str, prefix: str) -> str:
        """
        Generate a cache key for tracking login attempts.

        Args:
            identity: Username or email
            prefix: Cache key prefix

        Returns:
            Cache key string
        """
        return f"{prefix}{identity}"

    def _mark_login_attempt(self, identity: str, request: HttpRequest) -> None:
        """
        Mark that a login attempt is being made.

        Args:
            identity: Username or email
            request: The HTTP request
        """
        if not identity:
            return

        # Log the attempt
        logger.info(
            "Login attempt",
            extra={
                "ip_address": self._get_client_ip(request),
                "path": request.path,
                "identity": identity,
            },
        )

    def _register_failed_attempt(self, identity: str, request: HttpRequest) -> None:
        """
        Register a failed login attempt and potentially lock the account.

        Args:
            identity: Username or email
            request: The HTTP request
        """
        if not identity:
            return

        ip_address = self._get_client_ip(request)
        cache_key = self._get_cache_key(identity, CACHE_PREFIX)

        # Get current attempts or initialize
        attempts = cache.get(cache_key, {"count": 0, "ips": []})

        # Increment counter and add this IP if not present
        attempts["count"] += 1
        if ip_address not in attempts["ips"]:
            attempts["ips"].append(ip_address)

        # Store back in cache with expiry
        cache.set(cache_key, attempts, timeout=self.reset_after * 60)

        logger.warning(
            f"Failed login attempt {attempts['count']}/{self.max_attempts}",
            extra={
                "ip_address": ip_address,
                "path": request.path,
                "identity": identity,
                "attempts": attempts["count"],
                "max_attempts": self.max_attempts,
            },
        )

        # Lock account if max attempts reached
        if attempts["count"] >= self.max_attempts:
            self._lock_account(identity, attempts["ips"])

    def _lock_account(self, identity: str, ip_addresses: list) -> None:
        """
        Lock an account after too many failed attempts.

        Args:
            identity: Username or email
            ip_addresses: List of IP addresses that attempted login
        """
        lockout_key = self._get_cache_key(identity, LOCKOUT_PREFIX)

        # Record lockout with timestamp and IPs
        lockout_data = {
            "locked_at": timezone.now().isoformat(),
            "ip_addresses": ip_addresses,
        }

        # Set lock with expiry
        cache.set(lockout_key, lockout_data, timeout=self.lockout_duration * 60)

        logger.warning(
            f"Account locked due to {self.max_attempts} failed login attempts",
            extra={
                "identity": identity,
                "ip_addresses": ip_addresses,
                "lockout_duration": self.lockout_duration,
            },
        )

        # Reset failed attempts counter since we've now locked the account
        cache.delete(self._get_cache_key(identity, CACHE_PREFIX))

        # Optionally, notify admin or user about the lockout
        self._notify_lockout(identity, lockout_data)

    def _is_account_locked(self, identity: str, request: HttpRequest) -> bool:
        """
        Check if an account is currently locked.

        Args:
            identity: Username or email
            request: The HTTP request

        Returns:
            True if account is locked, False otherwise
        """
        lockout_key = self._get_cache_key(identity, LOCKOUT_PREFIX)
        lockout_data = cache.get(lockout_key)

        if lockout_data:
            # Account is locked
            ip_address = self._get_client_ip(request)

            # Record this attempt
            if ip_address not in lockout_data.get("ip_addresses", []):
                lockout_data["ip_addresses"].append(ip_address)
                cache.set(lockout_key, lockout_data, timeout=self.lockout_duration * 60)

            return True

        return False

    def _notify_lockout(self, identity: str, lockout_data: Dict[str, Any]) -> None:
        """
        Notify administrators about account lockout.

        Args:
            identity: Username or email
            lockout_data: Lockout information including IPs and timestamp
        """
        # This could send an email, push to a monitoring service, etc.
        # For now, just log the event
        if not get_config("ACCOUNT_LOCKOUT_NOTIFICATIONS", False):
            return

        logger.error(
            "SECURITY ALERT: Account locked due to repeated login failures",
            extra={
                "identity": identity,
                "lockout_data": lockout_data,
                "alert_type": "account_lockout",
            },
        )

        # Here you could add code to send email alerts, push to Slack, etc.
