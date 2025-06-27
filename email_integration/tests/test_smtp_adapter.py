"""
Integration tests for SMTP email adapter.

These tests verify the behavior of the SMTP adapter using a mock SMTP server
to simulate the actual email server responses.
"""

import os
import tempfile
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase

from ..channels.adapters.smtp import SMTPAdapter
from ..exceptions import AuthenticationError, ConnectionError, SendError
from ..models import Attachment
from .factories import EmailAccountFactory


class MockSMTPServer:
    """Mock implementation of the SMTP server protocol for testing."""

    def __init__(self, should_fail=False, auth_fail=False, send_fail=False):
        """Initialize the mock server."""
        self.should_fail = should_fail
        self.auth_fail = auth_fail
        self.send_fail = send_fail
        self.connected = False
        self.authenticated = False
        self.sent_messages = []

        # Track method calls for verification
        self.calls = []

    def _record_call(self, method, *args, **kwargs):
        """Record a method call for later verification."""
        self.calls.append({"method": method, "args": args, "kwargs": kwargs})

    def __call__(self, host, port=25, local_hostname=None, timeout=None):
        """Called when instantiating an SMTP or SMTP_SSL connection."""
        self._record_call("__call__", host, port, local_hostname, timeout)

        if self.should_fail:
            raise ConnectionError(f"Failed to connect to {host}:{port}")

        self.connected = True
        return self

    def ehlo(self):
        """Process EHLO command."""
        self._record_call("ehlo")
        return (250, "OK")

    def starttls(self, context=None):
        """Start TLS encryption."""
        self._record_call("starttls", context)
        return (220, "Ready to start TLS")

    def login(self, username, password):
        """Authenticate with the server."""
        self._record_call("login", username, password)
        if self.auth_fail:
            raise Exception("Authentication failed")
        self.authenticated = True
        return (235, "Authentication successful")

    def send_message(self, message, from_addr=None, to_addrs=None):
        """Send a message."""
        self._record_call("send_message", message, from_addr, to_addrs)

        if self.send_fail:
            raise Exception("Failed to send message")

        # Store the sent message for later verification
        self.sent_messages.append(
            {"message": message, "from_addr": from_addr, "to_addrs": to_addrs}
        )

        return {}  # Empty dict means no errors

    def sendmail(self, from_addr, to_addrs, msg, mail_options=None, rcpt_options=None):
        """Send mail without using Message object."""
        self._record_call("sendmail", from_addr, to_addrs, msg)

        if self.send_fail:
            raise Exception("Failed to send message")

        # Store the sent message for later verification
        self.sent_messages.append(
            {"from_addr": from_addr, "to_addrs": to_addrs, "msg": msg}
        )

        return {}  # Empty dict means no errors

    def quit(self):
        """Close connection and commit sent messages."""
        self._record_call("quit")
        self.connected = False
        self.authenticated = False
        return (221, "Bye")

    def close(self):
        """Close connection without committing."""
        self._record_call("close")
        self.connected = False
        self.authenticated = False


class SMTPAdapterTest(TestCase):
    """Test the SMTP adapter with a mock server."""

    def setUp(self):
        """Set up testing environment."""
        # Create a test account with SMTP settings
        self.account = EmailAccountFactory(
            email_address="sender@example.com", name="Test Sender"
        )

        # Add SMTP specific settings
        self.account.server_settings = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "sender@example.com",
            "smtp_password": "testpassword",
            "use_tls": True,
        }
        self.account.save()

        # Start mocking
        # Need to patch both SMTP and SMTP_SSL since we might use either
        self.mock_server = MockSMTPServer()

        self.smtp_patcher = mock.patch("smtplib.SMTP", self.mock_server)
        self.smtp_ssl_patcher = mock.patch("smtplib.SMTP_SSL", self.mock_server)

        self.mock_smtp = self.smtp_patcher.start()
        self.mock_smtp_ssl = self.smtp_ssl_patcher.start()

        # Create the adapter instance
        self.adapter = SMTPAdapter(self.account)

        # Create a temporary directory for attachment files
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after tests."""
        self.smtp_patcher.stop()
        self.smtp_ssl_patcher.stop()

        # Clean up temporary files
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                os.unlink(os.path.join(root, file))
        os.rmdir(self.temp_dir)

    def test_connect_success(self):
        """Test successful connection to SMTP server."""
        # Connect should succeed
        self.adapter.connect()

        # Verify connection was established
        self.assertTrue(self.mock_server.connected)
        self.assertTrue(self.mock_server.authenticated)

        # Verify server was called with correct parameters
        self.assertEqual(self.mock_server.calls[0]["method"], "__call__")
        self.assertEqual(self.mock_server.calls[0]["args"][0], "smtp.example.com")
        self.assertEqual(self.mock_server.calls[0]["args"][1], 587)

    def test_connect_auth_error(self):
        """Test authentication error handling."""
        # Configure mock to fail authentication
        self.mock_server.auth_fail = True

        # Connect should raise AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.adapter.connect()

        # Verify proper calls were made despite failure
        self.assertTrue(
            any(call["method"] == "login" for call in self.mock_server.calls)
        )

    def test_send_text_email(self):
        """Test sending a simple text email."""
        # Connect first
        self.adapter.connect()

        # Prepare email data
        email_data = {
            "to": "recipient@example.com",
            "subject": "Test Email",
            "body": "This is a test email.",
            "cc": "cc@example.com",
            "bcc": "bcc@example.com",
        }

        # Send the email
        result = self.adapter.send_email(**email_data)

        # Verify success
        self.assertTrue(result["success"])

        # Verify a message was sent
        self.assertEqual(len(self.mock_server.sent_messages), 1)

        # Check if quit was called to commit the send
        self.assertTrue(
            any(call["method"] == "quit" for call in self.mock_server.calls)
        )

        # For send_message, we need to verify the message content
        sent_message = self.mock_server.sent_messages[0].get("message")
        if sent_message:
            self.assertEqual(sent_message["Subject"], "Test Email")
            self.assertEqual(sent_message["From"], "Test Sender <sender@example.com>")
            self.assertEqual(sent_message["To"], "recipient@example.com")
            self.assertEqual(sent_message["Cc"], "cc@example.com")

    def test_send_html_email(self):
        """Test sending an HTML email."""
        # Connect first
        self.adapter.connect()

        # Prepare email data with HTML
        email_data = {
            "to": "recipient@example.com",
            "subject": "HTML Test Email",
            "body": "<p>This is an <strong>HTML</strong> test email.</p>",
            "html_body": True,
        }

        # Send the email
        result = self.adapter.send_email(**email_data)

        # Verify success
        self.assertTrue(result["success"])

        # Check content type in sent message
        sent_message = self.mock_server.sent_messages[0].get("message")
        if sent_message:
            # Should be multipart for HTML emails
            self.assertTrue(sent_message.is_multipart())

            # Find the HTML part
            html_part = None
            for part in sent_message.walk():
                if part.get_content_type() == "text/html":
                    html_part = part
                    break

            # Verify HTML part exists and has correct content
            self.assertIsNotNone(html_part)
            self.assertIn("text/html", html_part.get("Content-Type", ""))

    def test_send_with_attachments(self):
        """Test sending an email with attachments."""
        # Connect first
        self.adapter.connect()

        # Create test attachments
        attachments = []

        # PDF attachment
        pdf_attachment = Attachment(
            name="test.pdf", content_type="application/pdf", size=100
        )
        pdf_attachment.file.save("test.pdf", ContentFile(b"Test PDF content"))
        attachments.append(pdf_attachment)

        # Text attachment
        text_attachment = Attachment(
            name="test.txt", content_type="text/plain", size=50
        )
        text_attachment.file.save("test.txt", ContentFile(b"Test text content"))
        attachments.append(text_attachment)

        # Prepare email data with attachments
        email_data = {
            "to": "recipient@example.com",
            "subject": "Email with Attachments",
            "body": "This email has attachments.",
            "attachments": attachments,
        }

        # Send the email
        result = self.adapter.send_email(**email_data)

        # Verify success
        self.assertTrue(result["success"])

        # Check multipart message in sent message
        sent_message = self.mock_server.sent_messages[0].get("message")
        if sent_message:
            # Should be multipart for attachments
            self.assertTrue(sent_message.is_multipart())

            # Count attachments
            attachment_parts = []
            for part in sent_message.walk():
                disposition = part.get("Content-Disposition", "")
                if "attachment" in disposition:
                    attachment_parts.append(part)

            # Verify attachment count
            self.assertEqual(len(attachment_parts), 2)

            # Verify attachment filenames
            filenames = [part.get_filename() for part in attachment_parts]
            self.assertIn("test.pdf", filenames)
            self.assertIn("test.txt", filenames)

    def test_send_failure(self):
        """Test handling of send failures."""
        # Configure mock to fail sending
        self.mock_server.send_fail = True

        # Connect first
        self.adapter.connect()

        # Prepare email data
        email_data = {
            "to": "recipient@example.com",
            "subject": "Test Email",
            "body": "This is a test email.",
        }

        # Send should raise SendError
        with self.assertRaises(SendError):
            self.adapter.send_email(**email_data)

        # Verify no messages were successfully sent
        self.assertEqual(len(self.mock_server.sent_messages), 0)

    def test_connection_error(self):
        """Test connection error handling."""
        # Configure mock to fail connection
        self.mock_server.should_fail = True

        # Connect should raise ConnectionError
        with self.assertRaises(ConnectionError):
            self.adapter.connect()

    def test_reconnect_on_closed_connection(self):
        """Test ability to reconnect if connection is closed."""
        # Connect first
        self.adapter.connect()

        # Close the connection to simulate timeout or server disconnect
        self.mock_server.close()
        self.assertFalse(self.mock_server.connected)

        # Prepare email data
        email_data = {
            "to": "recipient@example.com",
            "subject": "Test Email After Reconnect",
            "body": "This is a test email after reconnection.",
        }

        # Should reconnect automatically
        result = self.adapter.send_email(**email_data)

        # Verify success
        self.assertTrue(result["success"])

        # Verify message was sent
        self.assertEqual(len(self.mock_server.sent_messages), 1)


class SMTPAdapterWithSSLTest(TestCase):
    """Test the SMTP adapter with SSL configuration."""

    def setUp(self):
        """Set up testing environment."""
        # Create a test account with SMTP SSL settings
        self.account = EmailAccountFactory()
        self.account.server_settings = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 465,
            "smtp_username": "sender@example.com",
            "smtp_password": "testpassword",
            "use_ssl": True,
            "use_tls": False,
        }
        self.account.save()

        # Mock server
        self.mock_server = MockSMTPServer()

        # Only need to patch SMTP_SSL for direct SSL connections
        self.smtp_ssl_patcher = mock.patch("smtplib.SMTP_SSL", self.mock_server)
        self.mock_smtp_ssl = self.smtp_ssl_patcher.start()

        # Create adapter
        self.adapter = SMTPAdapter(self.account)

    def tearDown(self):
        """Clean up after tests."""
        self.smtp_ssl_patcher.stop()

    def test_ssl_connection(self):
        """Test direct SSL connection without STARTTLS."""
        # Connect
        self.adapter.connect()

        # Verify connection was established
        self.assertTrue(self.mock_server.connected)

        # Verify SMTP_SSL was called with correct parameters
        self.assertEqual(self.mock_server.calls[0]["method"], "__call__")
        self.assertEqual(self.mock_server.calls[0]["args"][0], "smtp.example.com")
        self.assertEqual(self.mock_server.calls[0]["args"][1], 465)

        # Verify STARTTLS was NOT called
        self.assertFalse(
            any(call["method"] == "starttls" for call in self.mock_server.calls)
        )
