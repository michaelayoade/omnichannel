"""
Tests for WhatsApp webhook handlers and security verification.

This module focuses on testing the security aspects of webhook processing,
particularly signature verification and event type validation.
"""
import json
from unittest import mock

import pytest
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory

from whatsapp_integration.webhooks.handlers import (
    EVENT_TYPE_MESSAGE,
    EVENT_TYPE_STATUS,
    WebhookEventProcessor,
    WebhookSecurityVerifier,
    WebhookView,
)


class TestWebhookSecurity:
    """Test suite for webhook security verification."""

    @pytest.fixture
    def webhook_verifier(self):
        """Create a WebhookSecurityVerifier for testing."""
        return WebhookSecurityVerifier()

    @pytest.fixture
    def request_factory(self):
        """Create a RequestFactory for testing Django views."""
        return RequestFactory()

    def test_constants_usage(self):
        """Test that event type constants are properly defined."""
        assert EVENT_TYPE_MESSAGE == "messages", "Message event type constant is defined correctly"
        assert EVENT_TYPE_STATUS == "statuses", "Status event type constant is defined correctly"

        # Verify the processor uses the constants
        processor = WebhookEventProcessor()
        assert processor.event_types[EVENT_TYPE_MESSAGE], "Processor uses message constant"
        assert processor.event_types[EVENT_TYPE_STATUS], "Processor uses status constant"

    @mock.patch("django.conf.settings")
    def test_signature_verification(self, mock_settings, webhook_verifier):
        """Test webhook signature verification using SHA-256."""
        # Setup the test
        mock_settings.WHATSAPP_WEBHOOK_SECRET = "test-webhook-secret"
        payload = json.dumps({"test": "data"}).encode("utf-8")
        
        # Generate a valid signature
        valid_signature = webhook_verifier._generate_signature(payload)
        headers = {"X-Hub-Signature-256": f"sha256={valid_signature}"}
        
        # Test with valid signature
        assert webhook_verifier.verify_signature(payload, headers)
        
        # Test with invalid signature
        invalid_headers = {"X-Hub-Signature-256": "sha256=invalid-signature"}
        assert not webhook_verifier.verify_signature(payload, invalid_headers)
        
        # Test with missing signature
        assert not webhook_verifier.verify_signature(payload, {})

    @mock.patch("whatsapp_integration.webhooks.handlers.WebhookSecurityVerifier.verify_signature")
    def test_webhook_view_security(self, mock_verify, request_factory):
        """Test that WebhookView enforces signature verification."""
        # Setup
        view = WebhookView.as_view()
        payload = {"object": "whatsapp_business_account"}
        
        # Test with valid signature
        mock_verify.return_value = True
        request = request_factory.post(
            "/webhook/whatsapp/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = view(request)
        assert response.status_code == 200
        
        # Test with invalid signature
        mock_verify.return_value = False
        request = request_factory.post(
            "/webhook/whatsapp/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = view(request)
        assert response.status_code == 401  # Should be unauthorized

    @pytest.fixture
    def sample_processor(self):
        """Create a WebhookEventProcessor for testing."""
        processor = WebhookEventProcessor()
        # Mock the handler methods
        processor.handle_message = mock.Mock(return_value=True)
        processor.handle_status = mock.Mock(return_value=True)
        return processor

    def test_processor_event_routing(self, sample_processor):
        """Test that events are routed to the correct handlers."""
        # Message event
        message_event = {
            "type": EVENT_TYPE_MESSAGE,
            "data": {"message": "test"}
        }
        sample_processor.process_event(message_event)
        sample_processor.handle_message.assert_called_once_with(message_event)
        sample_processor.handle_status.assert_not_called()
        
        # Reset mocks
        sample_processor.handle_message.reset_mock()
        sample_processor.handle_status.reset_mock()
        
        # Status event
        status_event = {
            "type": EVENT_TYPE_STATUS,
            "data": {"status": "delivered"}
        }
        sample_processor.process_event(status_event)
        sample_processor.handle_status.assert_called_once_with(status_event)
        sample_processor.handle_message.assert_not_called()
        
        # Unknown event type
        unknown_event = {
            "type": "unknown",
            "data": {}
        }
        result = sample_processor.process_event(unknown_event)
        assert result is None
        sample_processor.handle_message.assert_not_called()
        sample_processor.handle_status.assert_not_called()
