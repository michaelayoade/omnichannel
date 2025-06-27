"""
Pytest configuration for WhatsApp integration tests.

This module provides pytest fixtures and configuration for testing
WhatsApp integration components with a focus on security.
"""
import os
from unittest import mock

import pytest
from django.conf import settings

# Mock environment variables for tests
@pytest.fixture(autouse=True)
def mock_test_settings():
    """
    Configure test settings with safe defaults.
    
    This prevents tests from accessing production credentials or services.
    """
    with mock.patch.dict(os.environ, {
        "WHATSAPP_API_VERSION": "v18.0",
        "WHATSAPP_ACCESS_TOKEN": "test-access-token",
        "WHATSAPP_PHONE_NUMBER_ID": "test-phone-number-id",
        "WHATSAPP_WEBHOOK_SECRET": "test-webhook-secret",
        "RATE_LIMIT_PER_MINUTE": "60",
        "RATE_LIMIT_BURST": "10",
    }):
        yield

@pytest.fixture
def sample_message_payload():
    """
    Return a sample WhatsApp message payload for testing.
    
    Uses representative test data rather than hardcoded production examples.
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "15551234567",
        "type": "text",
        "text": {
            "preview_url": False,
            "body": "Hello, this is a test message"
        }
    }

@pytest.fixture
def sample_webhook_payload():
    """Return a sample WhatsApp webhook payload for testing."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "test-account-id",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "123456789"
                    },
                    "messages": [{
                        "id": "test-message-id",
                        "from": "15559876543",
                        "timestamp": "1652171989",
                        "text": {
                            "body": "Hello, this is a test message"
                        },
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
