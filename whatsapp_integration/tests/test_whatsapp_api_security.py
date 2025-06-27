"""
Tests for WhatsApp API client security features.

This module contains tests that verify security features in the WhatsApp API client,
particularly rate limiting, exponential backoff, and hashing security improvements.
"""
import hashlib
import json
import time
from unittest import mock

import pytest
import requests

from whatsapp_integration.services.whatsapp_api import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_AFTER,
    EXPONENTIAL_BACKOFF_BASE,
    HTTP_STATUS_RATE_LIMITED,
    RateLimitExceeded,
    WhatsAppAPIError,
    WhatsAppBusinessAPI,
)


class TestWhatsAppAPISecurity:
    """Test WhatsApp API client security features."""

    @pytest.fixture
    def api_client(self):
        """Create a mock WhatsApp API client for testing."""
        return WhatsAppBusinessAPI(
            phone_number_id="1234567890",
            access_token="test-token",
        )

    @mock.patch("requests.request")
    def test_rate_limiting_detection(self, mock_request, api_client):
        """Test that rate limiting is properly detected and handled."""
        # Create a mock response with 429 status
        mock_response = mock.Mock()
        mock_response.status_code = HTTP_STATUS_RATE_LIMITED
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"error": {"message": "Rate limited"}}
        mock_request.return_value = mock_response

        # Verify that sending a message raises RateLimitExceeded after retries
        with pytest.raises(RateLimitExceeded):
            api_client.send_text_message(to="1234567890", text="Test message")

        # Check that we attempted the correct number of retries
        assert mock_request.call_count == DEFAULT_MAX_RETRIES

    @mock.patch("requests.request")
    @mock.patch("time.sleep", return_value=None)
    def test_exponential_backoff(self, mock_sleep, mock_request, api_client):
        """Test that exponential backoff is correctly implemented."""
        # First call fails with RequestException, second succeeds
        mock_request.side_effect = [
            requests.RequestException("Connection error"),
            mock.Mock(
                status_code=200,
                json=mock.Mock(return_value={"success": True}),
            ),
        ]

        result = api_client._make_request("GET", "/test")
        assert result == {"success": True}

        # Check that sleep was called with exponential backoff value
        mock_sleep.assert_called_once_with(EXPONENTIAL_BACKOFF_BASE**0)
        assert mock_request.call_count == 2

    @mock.patch("requests.request")
    def test_webhook_signature_security(self, mock_request):
        """Test webhook signature verification with secure hashing."""
        # Mock data for the webhook
        webhook_data = {"entry": [{"changes": [{"value": {"messages": []}}]}]}
        data_json = json.dumps(webhook_data).encode("utf-8")
        
        # Generate a proper HMAC signature with SHA-256
        from django.conf import settings
        from whatsapp_integration.webhooks.handlers import WebhookSecurityVerifier
        
        # Mock the settings
        with mock.patch("django.conf.settings") as mock_settings:
            mock_settings.WHATSAPP_WEBHOOK_SECRET = "test-webhook-secret"
            
            # Create a proper HMAC signature
            verifier = WebhookSecurityVerifier()
            signature = verifier._generate_signature(data_json)
            
            # Test verification
            headers = {"X-Hub-Signature-256": f"sha256={signature}"}
            is_valid = verifier.verify_signature(data_json, headers)
            
            assert is_valid, "Webhook signature verification should pass with valid signature"
            
            # Test with invalid signature
            headers = {"X-Hub-Signature-256": "sha256=invalid-signature"}
            is_valid = verifier.verify_signature(data_json, headers)
            
            assert not is_valid, "Webhook signature verification should fail with invalid signature"

    def test_security_constants(self):
        """Verify security-related constants are properly defined."""
        assert DEFAULT_MAX_RETRIES > 0, "Max retries should be positive"
        assert DEFAULT_RETRY_AFTER > 0, "Default retry time should be positive"
        assert EXPONENTIAL_BACKOFF_BASE > 1, "Backoff base should be greater than 1 for exponential growth"
        assert HTTP_STATUS_RATE_LIMITED == 429, "Rate limit HTTP status should be 429"
