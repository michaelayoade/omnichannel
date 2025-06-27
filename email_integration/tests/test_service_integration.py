"""
Integration tests for email service layer.
Tests the interaction between adapters, services, and tasks.
"""

import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from email_integration.models import Attachment, EmailMessage
from email_integration.services.email_processor import EmailProcessor
from email_integration.services.rule_engine import RuleEngine
from email_integration.tasks.polling import poll_email_account
from email_integration.tests.factories import (
    EmailAccountFactory,
    EmailMessageFactory,
    RuleFactory,
)


class TestEmailServiceIntegration(TestCase):
    """Integration tests for the email service layer."""

    def setUp(self):
        """Set up test environment."""
        # Create test accounts
        self.pop3_account = EmailAccountFactory(
            protocol="pop3",
            server_settings={
                "host": "pop3.example.com",
                "port": 995,
                "use_ssl": True,
            },
        )

        self.smtp_account = EmailAccountFactory(
            protocol="smtp",
            server_settings={
                "host": "smtp.example.com",
                "port": 587,
                "use_tls": True,
            },
        )

        self.gmail_account = EmailAccountFactory(
            protocol="gmail_api",
            oauth2_token={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": (datetime.now() + timedelta(hours=1)).timestamp(),
            },
        )

        # Create test rules
        self.rule = RuleFactory(
            account=self.pop3_account,
            name="Forward to Support",
            conditions={
                "subject_contains": ["support", "help"],
                "sender_email_matches": ["customer@example.com"],
            },
            actions={
                "forward_to": "support@company.com",
                "add_tags": ["support", "customer-inquiry"],
            },
            is_active=True,
        )

        # Create test processor
        self.processor = EmailProcessor()
        self.rule_engine = RuleEngine()

    @patch("email_integration.channels.adapters.pop3.POP3EmailAdapter")
    def test_email_fetch_and_process_flow(self, mock_adapter_class):
        """Test the full flow of fetching and processing emails."""
        # Setup mock POP3 adapter to return test emails
        mock_adapter = MagicMock()
        mock_adapter_class.return_value = mock_adapter

        # Mock email data
        email_data = {
            "message_id": "<test123@example.com>",
            "subject": "Need support with my account",
            "body": "This is a test email requesting support",
            "html_body": "<p>This is a test email requesting support</p>",
            "sender": "customer@example.com",
            "recipients": ["info@company.com"],
            "date": timezone.now(),
            "attachments": [
                {
                    "filename": "test.pdf",
                    "content": b"test pdf content",
                    "content_type": "application/pdf",
                    "size": 15,
                }
            ],
        }

        mock_adapter.fetch_messages.return_value = [email_data]

        # Execute the task that would normally be called by Celery
        with patch(
            "email_integration.channels.adapters.factory.get_adapter_for_account"
        ) as mock_get_adapter:
            mock_get_adapter.return_value = mock_adapter
            poll_email_account(self.pop3_account.id)

        # Verify email was saved to database
        self.assertEqual(EmailMessage.objects.count(), 1)
        saved_email = EmailMessage.objects.first()
        self.assertEqual(saved_email.subject, "Need support with my account")
        self.assertEqual(saved_email.sender, "customer@example.com")

        # Verify attachment was saved
        self.assertEqual(Attachment.objects.count(), 1)
        attachment = Attachment.objects.first()
        self.assertEqual(attachment.filename, "test.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.message, saved_email)

        # Verify rule was applied
        self.assertTrue(saved_email.tags.filter(name="support").exists())
        self.assertTrue(saved_email.tags.filter(name="customer-inquiry").exists())

    @patch("email_integration.services.email_sender.EmailSender.send")
    @patch("email_integration.channels.adapters.smtp.SMTPEmailAdapter")
    def test_rule_triggered_email_forwarding(self, mock_smtp_adapter_class, mock_send):
        """Test that rules properly trigger email forwarding."""
        mock_smtp_adapter = MagicMock()
        mock_smtp_adapter_class.return_value = mock_smtp_adapter

        # Create a test message that should trigger the rule
        message = EmailMessageFactory(
            account=self.pop3_account,
            subject="Please help with my account",
            sender="customer@example.com",
            direction="incoming",
        )

        # Apply rules to the message
        with patch(
            "email_integration.channels.adapters.factory.get_adapter_for_account"
        ) as mock_get_adapter:
            mock_get_adapter.return_value = mock_smtp_adapter
            self.rule_engine.process_message(message)

        # Verify the message was forwarded
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs["to"], ["support@company.com"])
        self.assertTrue("forward" in kwargs["subject"].lower())

    @patch("email_integration.channels.adapters.gmail_api.GmailAPIAdapter")
    @patch("email_integration.channels.adapters.factory.get_adapter_for_account")
    def test_api_adapter_message_handling(
        self, mock_get_adapter, mock_gmail_adapter_class
    ):
        """Test that API-based adapters correctly handle messages."""
        mock_gmail_adapter = MagicMock()
        mock_gmail_adapter_class.return_value = mock_gmail_adapter
        mock_get_adapter.return_value = mock_gmail_adapter

        # Setup mock Gmail API adapter
        email_data = {
            "message_id": "<gmail123@example.com>",
            "subject": "API Test Email",
            "body": "This is a test email from Gmail API",
            "html_body": "<p>This is a test email from Gmail API</p>",
            "sender": "sender@example.com",
            "recipients": ["recipient@company.com"],
            "date": timezone.now(),
            "thread_id": "thread_123",
            "labels": ["INBOX", "UNREAD"],
            "attachments": [],
        }

        mock_gmail_adapter.fetch_messages.return_value = [email_data]

        # Poll the account
        poll_email_account(self.gmail_account.id)

        # Verify the message was stored
        messages = EmailMessage.objects.filter(account=self.gmail_account)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages[0].subject, "API Test Email")
        self.assertEqual(messages[0].provider_data.get("thread_id"), "thread_123")

        # Verify metadata was preserved
        self.assertEqual(messages[0].provider_data.get("labels"), ["INBOX", "UNREAD"])

    @patch("email_integration.channels.adapters.factory.get_adapter_for_account")
    def test_error_handling_and_retry(self, mock_get_adapter):
        """Test error handling and retry behavior in the polling task."""
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        # Make the adapter raise an exception
        mock_adapter.fetch_messages.side_effect = ConnectionError("Connection failed")

        # Call the polling task directly - no retry in tests but should log error
        with patch("email_integration.tasks.polling.logger.error") as mock_logger:
            with self.assertRaises(ConnectionError):
                poll_email_account(self.pop3_account.id)

            # Verify the error was logged
            mock_logger.assert_called()

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    @patch("email_integration.channels.adapters.pop3.POP3EmailAdapter")
    def test_attachment_storage_and_retrieval(self, mock_adapter_class):
        """Test that file attachments are properly stored and retrieved."""
        mock_adapter = MagicMock()
        mock_adapter_class.return_value = mock_adapter

        # Create a test file
        test_content = b"test attachment content"

        # Create email with attachment
        email_data = {
            "message_id": "<attach123@example.com>",
            "subject": "Email with attachment",
            "body": "This email has an attachment",
            "sender": "sender@example.com",
            "recipients": ["recipient@company.com"],
            "date": timezone.now(),
            "attachments": [
                {
                    "filename": "document.pdf",
                    "content": test_content,
                    "content_type": "application/pdf",
                    "size": len(test_content),
                }
            ],
        }

        mock_adapter.fetch_messages.return_value = [email_data]

        # Process the email
        with patch(
            "email_integration.channels.adapters.factory.get_adapter_for_account"
        ) as mock_get_adapter:
            mock_get_adapter.return_value = mock_adapter
            poll_email_account(self.pop3_account.id)

        # Verify attachment
        message = EmailMessage.objects.get(subject="Email with attachment")
        self.assertEqual(message.attachments.count(), 1)

        attachment = message.attachments.first()
        self.assertEqual(attachment.filename, "document.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")

        # Verify file storage
        with open(attachment.file.path, "rb") as f:
            stored_content = f.read()

        self.assertEqual(stored_content, test_content)

    @patch("email_integration.services.rule_engine.RuleEngine.process_message")
    @patch("email_integration.channels.adapters.pop3.POP3EmailAdapter")
    def test_email_processing_pipeline(self, mock_adapter_class, mock_process_message):
        """Test that the entire email processing pipeline works correctly."""
        mock_adapter = MagicMock()
        mock_adapter_class.return_value = mock_adapter

        # Setup adapter to return emails
        email_data = {
            "message_id": "<pipeline123@example.com>",
            "subject": "Test Pipeline",
            "body": "Testing the full processing pipeline",
            "sender": "sender@example.com",
            "recipients": ["recipient@company.com"],
            "date": timezone.now(),
            "attachments": [],
        }

        mock_adapter.fetch_messages.return_value = [email_data]

        # Process the email through the polling task
        with patch(
            "email_integration.channels.adapters.factory.get_adapter_for_account"
        ) as mock_get_adapter:
            mock_get_adapter.return_value = mock_adapter
            poll_email_account(self.pop3_account.id)

        # Verify the message was processed
        message = EmailMessage.objects.filter(subject="Test Pipeline").first()
        self.assertIsNotNone(message)

        # Verify rule engine was called
        mock_process_message.assert_called_once()
        args = mock_process_message.call_args[0]
        self.assertEqual(args[0].id, message.id)
