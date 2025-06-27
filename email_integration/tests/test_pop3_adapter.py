"""Integration tests for POP3 email adapter.

These tests verify the behavior of the POP3 adapter using a mock POP3 server
to simulate the actual email server responses.
"""

import os
import tempfile
from datetime import datetime
from unittest import mock

import pytest
import responses
from django.test import TestCase

from ..channels.adapters.pop3 import POP3Adapter
from ..exceptions import AuthenticationError, ConnectionError
from .factories import EmailAccountFactory


class MockPOP3Server:
    """Mock implementation of the POP3 server protocol for testing."""

    def __init__(self, messages=None, should_fail=False, auth_fail=False):
        """Initialize the mock server."""
        self.messages = messages or []
        self.should_fail = should_fail
        self.auth_fail = auth_fail
        self.connected = False
        self.authenticated = False
        self.deleted_messages = set()

        # Track method calls for verification
        self.calls = []

    def _record_call(self, method, *args, **kwargs):
        """Record a method call for later verification."""
        self.calls.append({"method": method, "args": args, "kwargs": kwargs})

    def __call__(self, host, port=110, timeout=None):
        """Called when instantiating a POP3 or POP3_SSL connection."""
        self._record_call("__call__", host, port, timeout)

        if self.should_fail:
            raise ConnectionError(f"Failed to connect to {host}:{port}")

        self.connected = True
        return self

    def user(self, username):
        """Process USER command."""
        self._record_call("user", username)
        self.username = username
        if self.auth_fail:
            raise Exception("Authentication failed")
        return "+OK"

    def pass_(self, password):
        """Process PASS command."""
        self._record_call("pass_", password)
        if self.auth_fail:
            raise Exception("Authentication failed")
        self.authenticated = True
        return "+OK"

    def stat(self):
        """Return message count and size."""
        self._record_call("stat")
        # Return (message_count, mailbox_size)
        return (len(self.messages), sum(len(m) for m in self.messages))

    def list(self, which=None):
        """Return list of (message_number, message_size) tuples."""
        self._record_call("list", which)
        if which is not None:
            return (which, len(self.messages[which - 1]))

        return [
            (i + 1, len(m))
            for i, m in enumerate(self.messages)
            if i + 1 not in self.deleted_messages
        ]

    def retr(self, which):
        """Retrieve a message by number."""
        self._record_call("retr", which)
        if which > len(self.messages) or which <= 0:
            raise Exception(f"No such message: {which}")

        message = self.messages[which - 1]
        return ("+OK", message.split("\n"), len(message))

    def dele(self, which):
        """Mark a message for deletion."""
        self._record_call("dele", which)
        self.deleted_messages.add(which)
        return "+OK"

    def quit(self):
        """Close connection and remove deleted messages."""
        self._record_call("quit")
        self.connected = False
        self.authenticated = False
        return "+OK"

    def close(self):
        """Close connection without removing deleted messages."""
        self._record_call("close")
        self.connected = False
        self.authenticated = False


class POP3AdapterTest(TestCase):
    """Test the POP3 adapter with a mock server."""

    def setUp(self):
        """Set up testing environment."""
        # Create a test account with POP3 settings
        self.account = EmailAccountFactory(
            email_address="test@example.com", name="Test User",
        )

        # Add POP3 specific settings
        self.account.server_settings = {
            "pop3_server": "pop3.example.com",
            "pop3_port": 995,
            "pop3_username": "test@example.com",
            "pop3_password": "testpassword",
            "use_ssl": True,
            "leave_messages_on_server": False,
        }
        self.account.save()

        # Sample email messages for tests
        self.sample_messages = [
            f"""From: sender1@example.com
To: test@example.com
Subject: Test Email 1
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
Message-ID: <message1@example.com>
Content-Type: text/plain; charset="utf-8"

This is test email 1 content.
""",
            f"""From: sender2@example.com
To: test@example.com
Subject: Test Email 2
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
Message-ID: <message2@example.com>
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain; charset="utf-8"

This is test email 2 content with attachment.

--boundary
Content-Type: application/pdf; name="test.pdf"
Content-Disposition: attachment; filename="test.pdf"
Content-Transfer-Encoding: base64

dGVzdCBwZGYgY29udGVudA==

--boundary--
""",
        ]

        # Start the response mocking
        responses.start()

        # Patch the poplib module with our mock
        self.mock_server = MockPOP3Server(messages=self.sample_messages)

        # Need to patch both POP3 and POP3_SSL since we use SSL by default
        self.pop3_patcher = mock.patch("poplib.POP3", self.mock_server)
        self.pop3_ssl_patcher = mock.patch("poplib.POP3_SSL", self.mock_server)

        self.mock_pop3 = self.pop3_patcher.start()
        self.mock_pop3_ssl = self.pop3_ssl_patcher.start()

        # Create the adapter instance
        self.adapter = POP3Adapter(self.account)

    def tearDown(self):
        """Clean up after tests."""
        responses.stop()
        responses.reset()
        self.pop3_patcher.stop()
        self.pop3_ssl_patcher.stop()

    def test_connect_success(self):
        """Test successful connection to POP3 server."""
        # Connect should succeed
        self.adapter.connect()

        # Verify connection was established
        assert self.mock_server.connected
        assert self.mock_server.authenticated

        # Verify server was called with correct parameters
        assert self.mock_server.calls[0]["method"] == "__call__"
        assert self.mock_server.calls[0]["args"][0] == "pop3.example.com"
        assert self.mock_server.calls[0]["args"][1] == 995

    def test_connect_auth_error(self):
        """Test authentication error handling."""
        # Configure mock to fail authentication
        self.mock_server.auth_fail = True

        # Connect should raise AuthenticationError
        with pytest.raises(AuthenticationError):
            self.adapter.connect()

        # Verify proper calls were made despite failure
        assert any(call["method"] == "user" for call in self.mock_server.calls)

    def test_fetch_messages(self):
        """Test fetching messages from POP3 server."""
        # Connect first
        self.adapter.connect()

        # Fetch messages
        messages = self.adapter.fetch_messages(limit=10)

        # Verify results
        assert len(messages) == 2
        assert messages[0]["subject"] == "Test Email 1"
        assert messages[0]["from_email"] == "sender1@example.com"
        assert messages[1]["subject"] == "Test Email 2"

        # Verify message body content was extracted
        assert "This is test email 1 content." in messages[0]["body"]

        # Verify attachment was processed in the second message
        assert len(messages[1]["attachments"]) == 1
        assert messages[1]["attachments"][0].name == "test.pdf"
        assert messages[1]["attachments"][0].content_type == "application/pdf"

    def test_fetch_and_delete(self):
        """Test fetching and deleting messages."""
        # Connect first
        self.adapter.connect()

        # Set delete after fetching
        self.adapter.delete_after_fetch = True

        # Fetch messages
        self.adapter.fetch_messages(limit=10)

        # Verify messages were deleted
        assert len(self.mock_server.deleted_messages) == 2
        assert 1 in self.mock_server.deleted_messages
        assert 2 in self.mock_server.deleted_messages

        # Verify quit was called to commit deletions
        assert any(call["method"] == "quit" for call in self.mock_server.calls)

    def test_fetch_with_leave_on_server(self):
        """Test fetching messages with leave_messages_on_server option."""
        # Update account setting to leave messages on server
        self.account.server_settings["leave_messages_on_server"] = True
        self.account.save()

        # Reinitialize adapter with updated account
        self.adapter = POP3Adapter(self.account)

        # Connect and fetch
        self.adapter.connect()
        self.adapter.fetch_messages(limit=10)

        # Verify messages were not deleted
        assert len(self.mock_server.deleted_messages) == 0

    def test_connection_error(self):
        """Test connection error handling."""
        # Configure mock to fail connection
        self.mock_server.should_fail = True

        # Connect should raise ConnectionError
        with pytest.raises(ConnectionError):
            self.adapter.connect()


class POP3AdapterWithTempFilesTest(TestCase):
    """Test POP3 adapter attachment handling with real temporary files."""

    def setUp(self):
        """Set up testing environment."""
        # Create a test account with POP3 settings
        self.account = EmailAccountFactory()
        self.account.server_settings = {
            "pop3_server": "pop3.example.com",
            "pop3_port": 995,
            "pop3_username": "test@example.com",
            "pop3_password": "testpassword",
            "use_ssl": True,
        }
        self.account.save()

        # Create a temporary directory for files
        self.temp_dir = tempfile.mkdtemp()

        # Sample message with attachment
        self.message_with_attachment = f"""From: sender@example.com
To: test@example.com
Subject: Attachment Test
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}
Message-ID: <message-with-attachment@example.com>
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain; charset="utf-8"

Email with attachment.

--boundary
Content-Type: application/pdf; name="test.pdf"
Content-Disposition: attachment; filename="test.pdf"
Content-Transfer-Encoding: base64

dGVzdCBwZGYgY29udGVudA==

--boundary--
"""

        # Mock server with our test message
        self.mock_server = MockPOP3Server(messages=[self.message_with_attachment])

        # Patch poplib
        self.pop3_ssl_patcher = mock.patch("poplib.POP3_SSL", self.mock_server)
        self.mock_pop3_ssl = self.pop3_ssl_patcher.start()

        # Create adapter
        self.adapter = POP3Adapter(self.account)

    def tearDown(self):
        """Clean up after tests."""
        self.pop3_ssl_patcher.stop()

        # Clean up temporary files
        for root, _dirs, files in os.walk(self.temp_dir):
            for file in files:
                os.unlink(os.path.join(root, file))
        os.rmdir(self.temp_dir)

    def test_attachment_file_creation(self):
        """Test that attachment files are created correctly."""
        # Connect and fetch
        self.adapter.connect()
        messages = self.adapter.fetch_messages()

        # Verify we got one message with one attachment
        assert len(messages) == 1
        assert len(messages[0]["attachments"]) == 1

        attachment = messages[0]["attachments"][0]

        # Verify attachment metadata
        assert attachment.name == "test.pdf"
        assert attachment.content_type == "application/pdf"

        # Verify file content was saved
        assert attachment.file is not None

        # Read content and verify
        attachment.file.seek(0)
        content = attachment.file.read()
        assert content == b"test pdf content"
