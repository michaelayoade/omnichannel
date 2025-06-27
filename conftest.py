"""
Global pytest configuration and fixtures.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from email_integration.tests.factories import (
    EmailAccountFactory,
    EmailMessageFactory,
    RuleFactory,
)


@pytest.fixture
def api_client():
    """Return an API client for testing API endpoints."""
    return APIClient()


@pytest.fixture
def django_client():
    """Return a Django test client."""
    return Client()


@pytest.fixture
def admin_user(db):
    """Create and return a superuser for testing."""
    User = get_user_model()
    user = User.objects.create_superuser(
        username="admin", email="admin@example.com", password="securepassword"  # nosec B106
    )
    return user


@pytest.fixture
def authenticated_client(admin_user):
    """Return an authenticated API client."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def mock_request_id():
    """Return a consistent request ID for testing."""
    return "test-request-id-12345"


@pytest.fixture
def email_account(db):
    """Create and return a test email account."""
    return EmailAccountFactory()


@pytest.fixture
def email_message(db, email_account):
    """Create and return a test email message."""
    return EmailMessageFactory(account=email_account)


@pytest.fixture
def email_rule(db, email_account):
    """Create and return a test email rule."""
    return RuleFactory(account=email_account)


@pytest.fixture
def mock_settings(settings):
    """Configure test-specific settings."""
    # Email settings for testing
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    # Cache settings for testing
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }

    # Media settings for testing
    settings.MEDIA_ROOT = settings.BASE_DIR / "test_media"

    return settings
