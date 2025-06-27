"""
Integration tests for API-based email adapters.

These tests verify the behavior of the Gmail and Outlook API adapters
using mock servers to simulate the actual API responses.
"""

import base64
from datetime import datetime
from unittest import mock

import responses
from django.test import TestCase

from ..channels.adapters.gmail import GmailAdapter
from ..channels.adapters.outlook import OutlookAdapter
from ..exceptions import AuthenticationError
from ..models import EmailAccount
from ..tests.factories import EmailAccountFactory


class MockAPITestCase(TestCase):
    """Base test case for API adapter tests with response mocking."""

    def setUp(self):
        """Set up test environment."""
        # Create a test account with mock OAuth2 credentials
        self.account = EmailAccountFactory(
            email_address="test@example.com", name="Test User"
        )

        # Create mock server settings with OAuth2 configuration
        self.server_settings = {
            "client_id": "mock-client-id",
            "client_secret": "mock-client-secret",
            "refresh_token": "mock-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "api_type": "gmail",  # or 'outlook'
        }

        # Use the responses library to mock API responses
        responses.start()

    def tearDown(self):
        """Clean up after tests."""
        responses.stop()
        responses.reset()


class GmailAdapterTest(MockAPITestCase):
    """Tests for the Gmail API adapter."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()

        # Update account with Gmail-specific settings
        self.account.server_settings = {
            "oauth2": {
                "client_id": "mock-client-id",
                "client_secret": "mock-client-secret",
                "refresh_token": "mock-refresh-token",
            },
            "api_type": "gmail",
        }
        self.account.save()

        # Create adapter instance
        self.adapter = GmailAdapter(self.account)

        # Mock get_credentials to return our test credentials
        self.credentials_patcher = mock.patch.object(
            EmailAccount,
            "get_credentials",
            return_value={
                "oauth2": {
                    "access_token": "mock-access-token",
                    "refresh_token": "mock-refresh-token",
                    "client_id": "mock-client-id",
                    "client_secret": "mock-client-secret",
                }
            },
        )
        self.mock_get_credentials = self.credentials_patcher.start()

        # Mock Google API client
        self.google_client_patcher = mock.patch("gmail.GmailAdapter.build")
        self.mock_build = self.google_client_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        super().tearDown()
        self.credentials_patcher.stop()
        self.google_client_patcher.stop()

    @responses.activate
    def test_connect_success(self):
        """Test successful connection to Gmail API."""
        # Mock the Gmail API user profile endpoint
        responses.add(
            responses.GET,
            "https://www.googleapis.com/gmail/v1/users/me/profile",
            json={"emailAddress": "test@example.com", "messagesTotal": 100},
            status=200,
        )

        # Mock the Gmail service
        mock_service = mock.MagicMock()
        mock_users = mock.MagicMock()
        mock_profile = mock.MagicMock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_users().getProfile.return_value = mock_profile
        mock_service.users.return_value = mock_users

        self.mock_build.return_value = mock_service

        # Connect should succeed
        self.adapter.connect()

        # Verify the service was created
        self.assertIsNotNone(self.adapter.service)
        self.mock_build.assert_called_once_with(
            "gmail", "v1", credentials=mock.ANY, cache_discovery=False
        )

    @responses.activate
    def test_connect_auth_error(self):
        """Test authentication error during connect."""
        # Mock authentication error
        mock_service = mock.MagicMock()
        mock_users = mock.MagicMock()

        # Make the getProfile call raise an HttpError with 401 status
        from googleapiclient.errors import HttpError

        mock_users().getProfile.side_effect = HttpError(
            resp=mock.Mock(status=401),
            content=b'{"error": "invalid_token"}',
        )
        mock_service.users.return_value = mock_users
        self.mock_build.return_value = mock_service

        # Connect should raise AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.adapter.connect()

    @responses.activate
    def test_fetch_messages(self):
        """Test fetching messages from Gmail."""
        # Mock message list response
        mock_list_response = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ],
            "resultSizeEstimate": 2,
        }

        # Mock raw message content (base64 encoded)
        raw_message = """
        From: sender@example.com
        To: test@example.com
        Subject: Test Subject
        Date: Mon, 21 Mar 2023 12:00:00 +0000
        Content-Type: multipart/alternative; boundary="boundary"

        --boundary
        Content-Type: text/plain

        This is a test message.

        --boundary
        Content-Type: text/html

        <p>This is a test message.</p>

        --boundary--
        """
        raw_message_b64 = base64.urlsafe_b64encode(raw_message.encode()).decode()

        # Mock detailed message responses
        mock_msg1 = {
            "id": "msg1",
            "threadId": "thread1",
            "raw": raw_message_b64,
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                ]
            },
        }

        mock_msg2 = {
            "id": "msg2",
            "threadId": "thread2",
            "raw": raw_message_b64,
            "payload": {
                "headers": [
                    {"name": "From", "value": "other@example.com"},
                    {"name": "Subject", "value": "Another Test"},
                ]
            },
        }

        # Create and configure mock service
        mock_service = mock.MagicMock()
        mock_users = mock.MagicMock()
        mock_messages = mock.MagicMock()
        mock_list = mock.MagicMock()
        mock_get = mock.MagicMock()

        # Configure list call
        mock_list.execute.return_value = mock_list_response
        mock_messages.list.return_value = mock_list

        # Configure get calls for each message
        mock_get1 = mock.MagicMock()
        mock_get1.execute.return_value = mock_msg1

        mock_get2 = mock.MagicMock()
        mock_get2.execute.return_value = mock_msg2

        # Create a side effect for messages().get() to return different mocks
        # depending on message ID
        def get_side_effect(userId, id, format):
            if id == "msg1":
                return mock_get1
            else:
                return mock_get2

        mock_messages.get.side_effect = get_side_effect

        # Connect the mock objects
        mock_users().messages.return_value = mock_messages
        mock_service.users.return_value = mock_users
        self.mock_build.return_value = mock_service

        # Connect the adapter first
        self.adapter.connect()

        # Fetch messages
        messages = self.adapter.fetch_messages(limit=2)

        # Verify results
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["external_id"], "msg1")
        self.assertEqual(messages[1]["external_id"], "msg2")

        # Verify API was called correctly
        mock_messages.list.assert_called_once_with(userId="me", q="", maxResults=2)

        mock_messages.get.assert_any_call(userId="me", id="msg1", format="raw")

        mock_messages.get.assert_any_call(userId="me", id="msg2", format="raw")

    @responses.activate
    def test_fetch_with_date_filter(self):
        """Test fetching messages with date filter."""
        # Configure mock as in test_fetch_messages
        # but verify the query includes a date filter
        mock_list_response = {"messages": [], "resultSizeEstimate": 0}

        mock_service = mock.MagicMock()
        mock_users = mock.MagicMock()
        mock_messages = mock.MagicMock()
        mock_list = mock.MagicMock()

        mock_list.execute.return_value = mock_list_response
        mock_messages.list.return_value = mock_list
        mock_users().messages.return_value = mock_messages
        mock_service.users.return_value = mock_users
        self.mock_build.return_value = mock_service

        # Connect the adapter first
        self.adapter.connect()

        # Use a specific date for filtering
        since_date = datetime(2023, 3, 15)

        # Fetch messages
        messages = self.adapter.fetch_messages(since_date=since_date)

        # Verify date filter was applied correctly
        mock_messages.list.assert_called_once_with(
            userId="me", q="after:2023/03/15", maxResults=mock.ANY
        )


class OutlookAdapterTest(MockAPITestCase):
    """Tests for the Outlook API adapter."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()

        # Update account with Outlook-specific settings
        self.account.server_settings = {
            "oauth2": {
                "client_id": "mock-client-id",
                "client_secret": "mock-client-secret",
                "refresh_token": "mock-refresh-token",
                "tenant_id": "common",
            },
            "api_type": "outlook",
        }
        self.account.save()

        # Create adapter instance
        self.adapter = OutlookAdapter(self.account)

        # Mock get_credentials to return our test credentials
        self.credentials_patcher = mock.patch.object(
            EmailAccount,
            "get_credentials",
            return_value={
                "oauth2": {
                    "access_token": "mock-access-token",
                    "refresh_token": "mock-refresh-token",
                    "client_id": "mock-client-id",
                    "client_secret": "mock-client-secret",
                    "tenant_id": "common",
                }
            },
        )
        self.mock_get_credentials = self.credentials_patcher.start()

        # Mock MSAL client
        self.msal_patcher = mock.patch("msal.ConfidentialClientApplication")
        self.mock_msal = self.msal_patcher.start()

        # Configure mock MSAL client to return a token
        mock_app = mock.MagicMock()
        mock_app.acquire_token_by_refresh_token.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        self.mock_msal.return_value = mock_app

    def tearDown(self):
        """Clean up after tests."""
        super().tearDown()
        self.credentials_patcher.stop()
        self.msal_patcher.stop()

    @responses.activate
    def test_connect_success(self):
        """Test successful connection to Outlook API."""
        # Mock the Microsoft Graph API user profile endpoint
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me",
            json={"userPrincipalName": "test@example.com", "displayName": "Test User"},
            status=200,
        )

        # Connect should succeed
        self.adapter.connect()

        # Verify a token was obtained
        self.assertIsNotNone(self.adapter.token)
        self.assertTrue("access_token" in self.adapter.token)

    @responses.activate
    def test_connect_auth_error(self):
        """Test authentication error during connect."""
        # Mock the Microsoft Graph API to return auth error
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me",
            json={
                "error": {
                    "code": "InvalidAuthenticationToken",
                    "message": "Access token is invalid",
                }
            },
            status=401,
        )

        # Connect should raise AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.adapter.connect()

    @responses.activate
    def test_fetch_messages(self):
        """Test fetching messages from Outlook API."""
        # First mock the token endpoint to ensure we have a valid token
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me",
            json={"userPrincipalName": "test@example.com"},
            status=200,
        )

        # Mock the messages endpoint
        message1 = {
            "id": "msg1",
            "conversationId": "conv1",
            "subject": "Test Subject",
            "receivedDateTime": "2023-03-21T12:00:00Z",
            "internetMessageId": "<msg1@example.com>",
            "from": {
                "emailAddress": {"address": "sender@example.com", "name": "Sender Name"}
            },
            "toRecipients": [
                {"emailAddress": {"address": "test@example.com", "name": "Test User"}}
            ],
            "ccRecipients": [],
            "body": {
                "contentType": "html",
                "content": "<p>This is a test message.</p>",
            },
            "hasAttachments": False,
        }

        message2 = {
            "id": "msg2",
            "conversationId": "conv2",
            "subject": "Another Test",
            "receivedDateTime": "2023-03-22T14:00:00Z",
            "internetMessageId": "<msg2@example.com>",
            "from": {
                "emailAddress": {"address": "other@example.com", "name": "Other Sender"}
            },
            "toRecipients": [
                {"emailAddress": {"address": "test@example.com", "name": "Test User"}}
            ],
            "ccRecipients": [],
            "body": {"contentType": "text", "content": "This is another test message."},
            "hasAttachments": False,
        }

        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me/messages?$top=20",
            json={"value": [message1, message2]},
            status=200,
        )

        # Connect first
        self.adapter.connect()

        # Fetch messages
        messages = self.adapter.fetch_messages(limit=20)

        # Verify results
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["external_id"], "msg1")
        self.assertEqual(messages[0]["subject"], "Test Subject")
        self.assertEqual(messages[0]["from_email"], "sender@example.com")
        self.assertEqual(messages[1]["external_id"], "msg2")
        self.assertEqual(messages[1]["subject"], "Another Test")

    @responses.activate
    def test_fetch_with_attachments(self):
        """Test fetching a message with attachments."""
        # First mock the token endpoint to ensure we have a valid token
        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me",
            json={"userPrincipalName": "test@example.com"},
            status=200,
        )

        # Mock a message with attachments
        message_with_attachment = {
            "id": "msg3",
            "conversationId": "conv3",
            "subject": "Message with Attachment",
            "receivedDateTime": "2023-03-23T10:00:00Z",
            "internetMessageId": "<msg3@example.com>",
            "from": {
                "emailAddress": {"address": "sender@example.com", "name": "Sender"}
            },
            "toRecipients": [
                {"emailAddress": {"address": "test@example.com", "name": "Test User"}}
            ],
            "body": {
                "contentType": "html",
                "content": "<p>This message has an attachment.</p>",
            },
            "hasAttachments": True,
        }

        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me/messages?$top=1",
            json={"value": [message_with_attachment]},
            status=200,
        )

        # Mock the attachments endpoint for this message
        attachment = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": "att1",
            "name": "test.pdf",
            "contentType": "application/pdf",
            "size": 12345,
            "isInline": False,
            "contentBytes": base64.b64encode(b"PDF test content").decode(),
        }

        responses.add(
            responses.GET,
            "https://graph.microsoft.com/v1.0/me/messages/msg3/attachments",
            json={"value": [attachment]},
            status=200,
        )

        # Connect first
        self.adapter.connect()

        # Fetch message with attachment
        messages = self.adapter.fetch_messages(limit=1)

        # Verify results
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["external_id"], "msg3")

        # Verify attachment was processed
        self.assertTrue(len(messages[0]["attachments"]) > 0)
        self.assertEqual(messages[0]["attachments"][0].name, "test.pdf")
        self.assertEqual(messages[0]["attachments"][0].content_type, "application/pdf")
