from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from . import services
from .channels.adapters.base import BaseInboundAdapter, BaseOutboundAdapter
from .enums import AccountStatus
from .exceptions import AuthenticationError, ConnectionError
from .models import (
    EmailAccount,
    EmailAttachment,
    EmailMessage,
    EmailRule,
    EmailTemplate,
)
from .rules_engine import execute_rule, rule_matches


class RulesEngineTestCase(TestCase):
    def setUp(self):
        """Set up basic data for all test cases."""
        self.account = EmailAccount.objects.create(
            email_address="test@example.com",
            display_name="Test Account",
            status="active",
        )
        self.message = EmailMessage.objects.create(
            account=self.account,
            subject="Test Subject: Important News",
            from_email="sender@domain.com",
            from_name="Sender Name",
            plain_body="This is the body of the test email.",
            received_at=timezone.now(),
        )
        self.template = EmailTemplate.objects.create(
            id=1,  # Predictable ID for tests
            name="Test Auto-Reply Template",
            template_type="auto_reply",
            subject="Re: {{ original_subject }}",
            plain_content="This is an automated response.",
        )
        self.mock_adapter = MagicMock(spec=BaseOutboundAdapter)
        self.mock_adapter.account = self.account

    def test_rule_matches_from_contains(self):
        """Verify 'from_contains' condition matches correctly."""
        rule = EmailRule(condition_type="from_contains", condition_value="sender@")
        self.assertTrue(rule_matches(rule, self.message))
        rule.condition_value = "nonexistent@"
        self.assertFalse(rule_matches(rule, self.message))

    def test_rule_matches_from_equals_case_insensitive(self):
        """Verify 'from_equals' condition is case-insensitive."""
        rule = EmailRule(
            condition_type="from_equals", condition_value="SENDER@DOMAIN.COM"
        )
        self.assertTrue(rule_matches(rule, self.message))
        rule.condition_value = "sender@domain.com.uk"
        self.assertFalse(rule_matches(rule, self.message))

    def test_rule_matches_subject_contains(self):
        """Verify 'subject_contains' condition matches correctly."""
        rule = EmailRule(
            condition_type="subject_contains", condition_value="important news"
        )
        self.assertTrue(rule_matches(rule, self.message))

    def test_rule_matches_body_contains(self):
        """Verify 'body_contains' condition matches correctly."""
        rule = EmailRule(condition_type="body_contains", condition_value="test email")
        self.assertTrue(rule_matches(rule, self.message))

    def test_rule_matches_has_attachment(self):
        """Verify 'has_attachment' condition is based on attachment existence."""
        rule = EmailRule(condition_type="has_attachment")
        # Message should initially have no attachments
        self.assertFalse(rule_matches(rule, self.message))

        # Create an attachment and re-check
        EmailAttachment.objects.create(
            message=self.message,
            filename="test_file.pdf",
            content_type="application/pdf",
            size=1024,
            file_path="attachments/test_file.pdf",
        )
        self.assertTrue(rule_matches(rule, self.message))

    def test_rule_matches_domain_equals(self):
        """Verify 'domain_equals' condition matches correctly."""
        rule = EmailRule(condition_type="domain_equals", condition_value="domain.com")
        self.assertTrue(rule_matches(rule, self.message))
        rule.condition_value = "another-domain.com"
        self.assertFalse(rule_matches(rule, self.message))

    def test_execute_rule_auto_reply(self):
        """Verify 'auto_reply' action calls the send method on the adapter."""
        rule = EmailRule(
            rule_type="auto_reply", action_data={"template_id": self.template.id}
        )
        execute_rule(self.mock_adapter, rule, self.message)
        self.mock_adapter.send.assert_called_once()

    def test_execute_rule_forward(self):
        """Verify 'forward' action calls the send_forward method on the adapter."""
        rule = EmailRule(
            rule_type="forward", action_data={"forward_to": ["admin@example.com"]}
        )
        execute_rule(self.mock_adapter, rule, self.message)
        self.mock_adapter.send.assert_called_once()

    def test_execute_rule_set_priority(self):
        """Verify 'priority' action changes the message priority."""
        self.assertEqual(self.message.priority, "normal")
        rule = EmailRule(rule_type="priority", action_data={"priority": "high"})
        execute_rule(self.mock_adapter, rule, self.message)
        self.message.refresh_from_db()
        self.assertEqual(self.message.priority, "high")

    @patch("email_integration.rules_engine.logger")
    def test_execute_rule_unknown_type(self, mock_logger):
        """Verify that an unknown rule type is logged and handled gracefully."""
        rule = EmailRule(rule_type="non_existent_action")
        execute_rule(self.mock_adapter, rule, self.message)
        mock_logger.warning.assert_called_once_with(
            "No handler for rule_type '%s'", "non_existent_action"
        )

    @patch("email_integration.rules_engine.logger")
    def test_execute_rule_action_exception(self, mock_logger):
        """Verify exceptions from the adapter are caught and logged."""
        self.mock_adapter.send.side_effect = Exception("SMTP Service is down")

        rule = EmailRule(
            rule_type="auto_reply", action_data={"template_id": self.template.id}
        )
        execute_rule(self.mock_adapter, rule, self.message)

        mock_logger.exception.assert_called_once()

        # The call is logger.exception(msg, rule.id, message.id, exc).
        # We need to check the exception object, which is the 4th element (index 3).
        logged_exception = mock_logger.exception.call_args.args[3]
        self.assertIn("SMTP Service is down", str(logged_exception))


class EmailIntegrationServiceTests(TestCase):
    def setUp(self):
        self.account = EmailAccount.objects.create(
            email_address="polltest@example.com",
            status=AccountStatus.ACTIVE,
            auto_polling_enabled=True,
            inbound_channel="IMAPService",  # Assuming IMAPService is a valid adapter key
        )

    @patch("email_integration.services.get_adapter")
    def test_poll_and_process_account_success(self, mock_get_adapter):
        """Test successful polling of an email account."""
        mock_adapter = MagicMock(spec=BaseInboundAdapter)
        mock_adapter.poll.return_value = MagicMock(
            messages_processed=5, messages_failed=0, status="success"
        )
        mock_get_adapter.return_value = mock_adapter

        result = services.poll_and_process_account(self.account.id)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["messages_processed"], 5)
        mock_get_adapter.assert_called_once_with("IMAPService", self.account)
        mock_adapter.poll.assert_called_once()

    @patch("email_integration.services.get_adapter")
    def test_poll_and_process_account_auth_error(self, mock_get_adapter):
        """Test that an AuthenticationError disables the account."""
        mock_adapter = MagicMock(spec=BaseInboundAdapter)
        mock_adapter.poll.side_effect = AuthenticationError("Invalid credentials")
        mock_get_adapter.return_value = mock_adapter

        result = services.poll_and_process_account(self.account.id)

        self.assertEqual(result["status"], "authentication_error")
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, AccountStatus.INACTIVE)
        self.assertIn("Authentication failed", self.account.last_error_message)

    @patch("email_integration.services.get_adapter")
    def test_poll_and_process_account_connection_error(self, mock_get_adapter):
        """Test that a ConnectionError is raised to allow for retries."""
        mock_adapter = MagicMock(spec=BaseInboundAdapter)
        mock_adapter.poll.side_effect = ConnectionError("Could not connect to server")
        mock_get_adapter.return_value = mock_adapter

        with self.assertRaises(ConnectionError):
            services.poll_and_process_account(self.account.id)

    def test_poll_and_process_non_existent_account(self):
        """Test polling a non-existent account raises DoesNotExist."""
        with self.assertRaises(EmailAccount.DoesNotExist):
            services.poll_and_process_account(99999)  # An ID that does not exist
