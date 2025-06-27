"""
Tests for security and rate limiting middleware.

This module tests the behavior of middleware components
for security headers, request ID tracking, content validation, and rate limiting.
"""

import time
import uuid
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from ..middleware.rate_limit import RateLimitMiddleware
from ..middleware.security import (
    ContentValidationMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


class MiddlewareTestCase(TestCase):
    """Base test case for middleware tests."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="user@example.com", password="password123"  # nosec B106
        )


class SecurityHeadersMiddlewareTest(MiddlewareTestCase):
    """Tests for SecurityHeadersMiddleware."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.middleware = SecurityHeadersMiddleware(lambda request: HttpResponse())

    def test_security_headers_added(self):
        """Test that security headers are properly added."""
        request = self.factory.get("/")
        response = self.middleware(request)

        # Check that security headers were added
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-XSS-Protection"], "1; mode=block")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_csp_header_in_production(self):
        """Test that CSP header is added in production."""
        # Mock settings.DEBUG = False for production environment
        with mock.patch("django.conf.settings.DEBUG", False):
            request = self.factory.get("/")
            response = self.middleware(request)

            # CSP should be present in production
            self.assertIn("Content-Security-Policy", response)
            self.assertIn("default-src 'self'", response["Content-Security-Policy"])

    def test_no_csp_header_in_debug(self):
        """Test that CSP header is omitted in debug mode."""
        # Mock settings.DEBUG = True for development environment
        with mock.patch("django.conf.settings.DEBUG", True):
            request = self.factory.get("/")
            response = self.middleware(request)

            # CSP should not be present in debug mode
            self.assertNotIn("Content-Security-Policy", response)


class RequestIDMiddlewareTest(MiddlewareTestCase):
    """Tests for RequestIDMiddleware."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.middleware = RequestIDMiddleware(lambda request: HttpResponse())

    def test_request_id_generated(self):
        """Test that a request ID is generated if not present."""
        request = self.factory.get("/")
        response = self.middleware(request)

        # Request should have an ID assigned
        self.assertTrue(hasattr(request, "request_id"))
        # Response should include the ID header
        self.assertIn("X-Request-ID", response)
        # IDs should match
        self.assertEqual(request.request_id, response["X-Request-ID"])

    def test_existing_request_id_used(self):
        """Test that an existing request ID is preserved."""
        test_id = str(uuid.uuid4())
        request = self.factory.get("/", HTTP_X_REQUEST_ID=test_id)
        response = self.middleware(request)

        # Request should have the provided ID
        self.assertEqual(request.request_id, test_id)
        # Response should return the same ID
        self.assertEqual(response["X-Request-ID"], test_id)

    @mock.patch("email_integration.middleware.security.logger")
    def test_logging_context(self, mock_logger):
        """Test that request context is added to logs."""
        request = self.factory.get("/")
        self.middleware(request)

        # Logger should have had context set with request ID
        mock_logger.set_context.assert_called_with(
            request_id=request.request_id, path=request.path
        )


class ContentValidationMiddlewareTest(MiddlewareTestCase):
    """Tests for ContentValidationMiddleware."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.get_response_mock = mock.MagicMock(return_value=HttpResponse())
        self.middleware = ContentValidationMiddleware(self.get_response_mock)

    def test_safe_methods_pass_through(self):
        """Test that safe methods pass through validation."""
        for method in ("GET", "HEAD", "OPTIONS"):
            request = getattr(self.factory, method.lower())("/")
            self.middleware(request)

            # The get_response should have been called
            self.get_response_mock.assert_called()
            self.get_response_mock.reset_mock()

    def test_safe_content_passes(self):
        """Test that safe content passes validation."""
        request = self.factory.post("/", {"safe_field": "safe content"})
        self.middleware(request)

        # The request should pass through
        self.get_response_mock.assert_called_once()

    def test_suspicious_content_blocked(self):
        """Test that suspicious content is blocked."""
        suspicious_content = [
            {"sql": "value' OR 1=1--"},
            {"xss": "<script>alert('XSS')</script>"},
            {"path": "../../../etc/passwd"},
        ]

        for data in suspicious_content:
            request = self.factory.post("/", data)
            response = self.middleware(request)

            # Should return 403 Forbidden
            self.assertEqual(response.status_code, 403)
            # Get response should not be called
            self.get_response_mock.assert_not_called()
            self.get_response_mock.reset_mock()

    @mock.patch("email_integration.middleware.security.logger")
    def test_suspicious_content_logged(self, mock_logger):
        """Test that suspicious content is logged."""
        request = self.factory.post("/", {"xss": "<script>alert('XSS')</script>"})
        request.request_id = "test-id"
        response = self.middleware(request)

        # Should log a warning
        mock_logger.warning.assert_called_with(
            "Suspicious content detected in request", extra=mock.ANY
        )

        # Check that the warning includes useful context
        extra = mock_logger.warning.call_args[1]["extra"]
        self.assertEqual(extra["request_id"], "test-id")
        self.assertEqual(extra["method"], "POST")


class RateLimitMiddlewareTest(MiddlewareTestCase):
    """Tests for RateLimitMiddleware."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Reset configuration for tests
        self.patcher = mock.patch("email_integration.middleware.rate_limit.get_config")
        self.mock_get_config = self.patcher.start()

        # Configure test rate limit (5 requests in 1 second window)
        self.mock_get_config.side_effect = lambda key, default: {
            "RATE_LIMIT_WINDOW": 1,  # 1 second window
            "RATE_LIMIT_MAX_REQUESTS": 5,  # 5 requests per window
            "RATE_LIMIT_ENABLED": True,
        }.get(key, default)

        self.middleware = RateLimitMiddleware(lambda request: HttpResponse())

    def tearDown(self):
        """Clean up after tests."""
        super().tearDown()
        self.patcher.stop()

    def test_exempt_paths_not_rate_limited(self):
        """Test that exempt paths are not rate limited."""
        for exempt_path in [
            "/admin/",
            "/static/file.js",
            "/media/image.png",
            "/health/check",
        ]:
            request = self.factory.get(exempt_path)
            request.user = AnonymousUser()

            # Make multiple requests that would normally exceed rate limit
            responses = []
            for _ in range(10):
                responses.append(self.middleware(request))

            # All responses should be successful
            for response in responses:
                self.assertEqual(response.status_code, 200)

    def test_anonymous_user_rate_limited(self):
        """Test that anonymous users are rate limited by IP."""
        request = self.factory.get("/api/endpoint")
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # First 5 requests should succeed
        for _ in range(5):
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

        # 6th request should be rate limited
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many requests", str(response.content))

    def test_authenticated_user_rate_limited(self):
        """Test that authenticated users are rate limited by user ID."""
        request1 = self.factory.get("/api/endpoint")
        request1.user = self.user
        request1.META["REMOTE_ADDR"] = "192.168.1.1"

        # Create a second user with same IP
        user2 = User.objects.create_user(
            username="testuser2", email="user2@example.com", password="password123"  # nosec B106
        )
        request2 = self.factory.get("/api/endpoint")
        request2.user = user2
        request2.META["REMOTE_ADDR"] = "192.168.1.1"

        # First user makes 5 requests
        for _ in range(5):
            response = self.middleware(request1)
            self.assertEqual(response.status_code, 200)

        # First user's 6th request is rate limited
        response = self.middleware(request1)
        self.assertEqual(response.status_code, 429)

        # Second user should still be able to make requests
        # even though they share the same IP
        for _ in range(5):
            response = self.middleware(request2)
            self.assertEqual(response.status_code, 200)

    def test_rate_limit_window(self):
        """Test that rate limit resets after time window."""
        request = self.factory.get("/api/endpoint")
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "192.168.1.2"

        # Make 5 requests (should succeed)
        for _ in range(5):
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

        # 6th request (should be limited)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)

        # Wait for rate limit window to expire
        time.sleep(1.1)  # Just over the 1-second window

        # Should be able to make requests again
        for _ in range(5):
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

    def test_disabled_rate_limit(self):
        """Test behavior when rate limiting is disabled."""
        # Disable rate limiting
        self.mock_get_config.side_effect = lambda key, default: {
            "RATE_LIMIT_WINDOW": 1,
            "RATE_LIMIT_MAX_REQUESTS": 5,
            "RATE_LIMIT_ENABLED": False,
        }.get(key, default)

        request = self.factory.get("/api/endpoint")
        request.user = AnonymousUser()

        # Make many requests (more than the limit)
        for _ in range(20):
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)
