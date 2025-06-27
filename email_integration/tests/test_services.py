"""
Integration tests for email_integration services.
"""

from unittest import mock

import pytest
from django.utils import timezone

from email_integration.channels.adapters.base import BaseInboundAdapter
from email_integration.enums import AccountStatus
from email_integration.exceptions import AuthenticationError, ConnectionError
from email_integration.models import EmailAccount, EmailMessage
from email_integration.services import poll_and_process_account


@pytest.fixture
def email_account(db):
    """Fixture for creating a test email account."""
    return EmailAccount.objects.create(
        email_address="test@example.com",
        status=AccountStatus.ACTIVE,
        auto_polling_enabled=True,
        poll_frequency=300,  # 5 minutes
        organization_id=1,
        server_settings={
            "imap_server": "imap.example.com",
            "imap_port": 993,
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
        },
    )


@pytest.fixture
def mock_adapter():
    """Fixture for creating a mock adapter."""
    mock_adapter = mock.MagicMock(spec=BaseInboundAdapter)
    mock_adapter.fetch_new_messages.return_value = [
        {
            "message_id": "test-message-1",
            "subject": "Test Subject",
            "sender": "sender@example.com",
            "recipient": "test@example.com",
            "body": "Test body content",
            "received_at": timezone.now(),
            "attachments": [],
        }
    ]
    return mock_adapter


@pytest.mark.django_db
def test_poll_and_process_account_success(email_account, mock_adapter):
    """Test successful polling and processing of an email account."""
    # Arrange
    with mock.patch(
        "email_integration.services.get_adapter", return_value=mock_adapter
    ):
        # Act
        result = poll_and_process_account(email_account.id)

        # Assert
        assert result["status"] == "success"
        assert result["account_id"] == email_account.id
        assert result["messages_processed"] == 1

        # Verify adapter was called correctly
        mock_adapter.authenticate.assert_called_once()
        mock_adapter.fetch_new_messages.assert_called_once()

        # Verify email account was updated
        email_account.refresh_from_db()
        assert email_account.last_poll_at is not None

        # Verify message was saved
        assert EmailMessage.objects.count() == 1


@pytest.mark.django_db
def test_poll_and_process_account_auth_error(email_account):
    """Test authentication error handling."""
    # Arrange
    mock_adapter = mock.MagicMock(spec=BaseInboundAdapter)
    mock_adapter.authenticate.side_effect = AuthenticationError("Invalid credentials")

    with mock.patch(
        "email_integration.services.get_adapter", return_value=mock_adapter
    ):
        # Act
        result = poll_and_process_account(email_account.id)

        # Assert
        assert result["status"] == "auth_error"
        assert result["account_id"] == email_account.id
        assert "error" in result

        # Verify email account status was updated
        email_account.refresh_from_db()
        assert email_account.status == AccountStatus.AUTH_ERROR


@pytest.mark.django_db
def test_poll_and_process_account_connection_error(email_account):
    """Test connection error handling."""
    # Arrange
    mock_adapter = mock.MagicMock(spec=BaseInboundAdapter)
    mock_adapter.authenticate.side_effect = ConnectionError("Server unreachable")

    with mock.patch(
        "email_integration.services.get_adapter", return_value=mock_adapter
    ):
        # Act & Assert (should raise ConnectionError for the task to retry)
        with pytest.raises(ConnectionError):
            poll_and_process_account(email_account.id)

        # Verify email account status remains active
        email_account.refresh_from_db()
        assert email_account.status == AccountStatus.ACTIVE
