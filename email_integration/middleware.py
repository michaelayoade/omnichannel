"""Security and logging middleware for the email integration app.

This module provides middleware components for:
- Adding security headers to responses
- Request validation
- Request ID tracking for structured logging
"""

import re
import uuid

from django.conf import settings
from django.http import HttpResponseForbidden

from omnichannel_core.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class SecurityHeadersMiddleware:
    """Middleware to add security headers to all responses.

    This middleware implements security best practices by adding
    appropriate security headers to all HTTP responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add security headers to all responses
        response["X-Content-Type-Options"] = "nosniff"
        response["X-XSS-Protection"] = "1; mode=block"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add Content-Security-Policy header in non-debug mode
        if not settings.DEBUG:
            # Adjust the CSP policy based on your specific requirements
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )

        return response


class RequestIDMiddleware:
    """Middleware to add a unique request ID to each request.

    This supports distributed tracing and structured logging by
    ensuring each request has a unique identifier that can be
    propagated through the system.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if request already has an ID from upstream service
        request_id = request.headers.get("X-Request-ID")

        # Create a new request ID if one doesn't exist
        if not request_id:
            request_id = str(uuid.uuid4())

        # Attach the ID to the request object
        request.request_id = request_id

        # Add context for all log messages in this request
        logger.set_context(request_id=request_id, path=request.path)

        # Log the request
        logger.info(
            "Request received",
            extra={
                "method": request.method,
                "path": request.path,
                "ip": self._get_client_ip(request),
            },
        )

        response = self.get_response(request)

        # Add the request ID to the response headers
        response["X-Request-ID"] = request_id

        # Log the response
        logger.info(
            "Response sent",
            extra={"status_code": response.status_code, "path": request.path},
        )

        return response

    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Get the first IP in case of multiple proxies
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class ContentValidationMiddleware:
    """Middleware to validate request content for security threats.

    This middleware scans request content for potentially malicious patterns
    like SQL injection or XSS attacks.
    """

    # Define patterns to check for
    SUSPICIOUS_PATTERNS = [
        # SQL injection patterns
        r"(?i)\b(union\s+select|drop\s+table|--\s|;--)",
        # XSS patterns
        r"(?i)<script>|<\/script>|javascript:",
        # Path traversal
        r"\.\.\/|\.\.\\",
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns for efficiency
        self.patterns = [re.compile(pattern) for pattern in self.SUSPICIOUS_PATTERNS]

    def __call__(self, request):
        # Skip validation for safe methods
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return self.get_response(request)

        # Check POST data
        if request.method == "POST":
            for _key, value in request.POST.items():
                if self._is_suspicious(value):
                    logger.warning(
                        "Suspicious content detected in request",
                        extra={
                            "request_id": getattr(request, "request_id", None),
                            "path": request.path,
                            "method": request.method,
                            "ip": self._get_client_ip(request),
                        },
                    )
                    return HttpResponseForbidden("Invalid request content")

        # Check JSON data if present
        if hasattr(request, "body") and request.content_type == "application/json":
            try:
                if self._is_suspicious(request.body.decode("utf-8")):
                    logger.warning(
                        "Suspicious content detected in JSON request",
                        extra={
                            "request_id": getattr(request, "request_id", None),
                            "path": request.path,
                            "method": request.method,
                        },
                    )
                    return HttpResponseForbidden("Invalid request content")
            except Exception as e:
                # Decoding or parsing error, log and continue processing
                logger.warning(f"Error processing request body: {e}")
                pass

        return self.get_response(request)

    def _is_suspicious(self, content):
        """Check if the content matches any suspicious patterns."""
        if not content or not isinstance(content, str):
            return False

        return any(pattern.search(content) for pattern in self.patterns)

    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
