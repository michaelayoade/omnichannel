"""Gmail API adapter implementation.

Provides email operations via the Gmail API, supporting OAuth2 authentication,
message fetching, and attachment handling.
"""

import base64
import uuid
from email import policy
from email.parser import BytesParser
from typing import Any

from django.core.files.base import ContentFile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from omnichannel_core.utils.logging import ContextLogger

from ...config import get_config
from ...exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    FetchError,
)
from ...models import Attachment
from ..adapters.base import BaseInboundAdapter
from ..utils import parse_mime_message

logger = ContextLogger(__name__)


class GmailAdapter(BaseInboundAdapter):
    """Gmail API adapter for sending and receiving emails.

    Uses OAuth2 authentication to access Gmail API for email operations.
    Provides functionality to fetch and parse messages.
    """

    def __init__(self, account):
        """Initialize the Gmail adapter with an email account.

        Args:
        ----
            account: The EmailAccount model instance

        """
        self.account = account
        self.service = None
        self.credentials = None
        self.max_results = get_config("MAX_MESSAGES_PER_POLL", 20)
        self.connection_timeout = get_config("DEFAULT_TIMEOUT", 30)
        self.request_id = str(uuid.uuid4())

        # Set up logging context
        logger.set_context(
            account_id=account.id,
            adapter="GmailAdapter",
            email_address=account.email_address,
            request_id=self.request_id,
        )

        # Check if required OAuth2 settings exist
        self._check_oauth2_config()

    def _check_oauth2_config(self) -> None:
        """Check if required OAuth2 configuration is available.

        Raises
        ------
            ConfigurationError: If OAuth2 configuration is missing

        """
        settings = self.account.server_settings or {}
        required_keys = ["client_id", "client_secret", "refresh_token"]

        for key in required_keys:
            if key not in settings:
                error_msg = f"Missing required OAuth2 setting: {key}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)

    def _get_credentials(self) -> Credentials:
        """Get OAuth2 credentials for Gmail API access.

        Returns
        -------
            Google OAuth2 Credentials object

        Raises
        ------
            AuthenticationError: If credentials cannot be obtained

        """
        try:
            credentials = self.account.get_credentials()
            oauth2 = credentials.get("oauth2", {})

            # Create Google Credentials object
            return Credentials(
                token=oauth2.get("access_token"),
                refresh_token=oauth2.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",  # nosec B106
                client_id=oauth2.get("client_id"),
                client_secret=oauth2.get("client_secret"),
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            )
        except Exception as e:
            error_msg = f"Failed to create OAuth2 credentials: {e!s}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

    def connect(self) -> None:
        """Connect to Gmail API by creating an authenticated service.

        Raises
        ------
            ConnectionError: If connection cannot be established
            AuthenticationError: If authentication fails

        """
        try:
            logger.info("Connecting to Gmail API")

            # Get credentials and build Gmail service
            self.credentials = self._get_credentials()
            self.service = build(
                "gmail", "v1", credentials=self.credentials, cache_discovery=False,
            )

            # Test connection by getting the user profile
            profile = self.service.users().getProfile(userId="me").execute()
            logger.debug(
                "Connected to Gmail API",
                extra={"email_address": profile.get("emailAddress")},
            )

        except AuthenticationError:
            # Re-raise authentication errors
            raise
        except HttpError as e:
            error_msg = f"Gmail API HTTP error: {e!s}"
            logger.error(error_msg)
            if e.status_code == 401:
                raise AuthenticationError(error_msg)
            else:
                raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Failed to connect to Gmail API: {e!s}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    def authenticate(self) -> None:
        """Authenticate to Gmail API.

        For Gmail API, authentication is handled during connect(),
        so this method just ensures we have a valid connection.

        Raises
        ------
            AuthenticationError: If authentication fails

        """
        if not self.service:
            self.connect()

    def fetch_messages(self, since_date=None, limit=None) -> list[dict[str, Any]]:
        """Fetch messages from Gmail.

        Args:
        ----
            since_date: Optional datetime to fetch messages since
            limit: Maximum number of messages to fetch

        Returns:
        -------
            List of parsed email message dictionaries

        Raises:
        ------
            FetchError: If messages cannot be fetched

        """
        if not self.service:
            self.connect()

        try:
            logger.info("Fetching messages from Gmail API")

            # Build query string for Gmail API
            query = ""
            if since_date:
                # Format date as YYYY/MM/DD
                date_str = since_date.strftime("%Y/%m/%d")
                query = f"after:{date_str}"

            # Set limit to configured max if not specified
            if not limit or limit > self.max_results:
                limit = self.max_results

            # Fetch message IDs first
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=limit)
                .execute()
            )

            messages = results.get("messages", [])
            message_count = len(messages)

            logger.debug(f"Found {message_count} messages from Gmail API")

            # Process and fetch full messages
            parsed_messages = []
            for msg_data in messages:
                message_id = msg_data.get("id")

                try:
                    # Fetch the full message with MIME content
                    full_msg = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=message_id, format="raw")
                        .execute()
                    )

                    # Parse the message
                    parsed_msg = self._parse_gmail_message(full_msg)
                    if parsed_msg:
                        parsed_messages.append(parsed_msg)

                except Exception as e:
                    logger.warning(f"Failed to process message {message_id}: {e!s}")
                    continue

            logger.info(
                f"Successfully fetched {len(parsed_messages)} messages from Gmail API",
            )
            return parsed_messages

        except HttpError as e:
            error_msg = f"Gmail API error fetching messages: {e!s}"
            logger.error(error_msg)
            raise FetchError(error_msg)

        except Exception as e:
            error_msg = f"Failed to fetch messages from Gmail API: {e!s}"
            logger.exception(error_msg)
            raise FetchError(error_msg)

    def _parse_gmail_message(
        self, gmail_message: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Parse a Gmail API message into our standard format.

        Args:
        ----
            gmail_message: Raw Gmail message from API

        Returns:
        -------
            Dictionary containing parsed email fields or None if parsing failed

        """
        try:
            # Get the raw message content and decode
            raw_msg = gmail_message.get("raw", "")
            if not raw_msg:
                return None

            msg_bytes = base64.urlsafe_b64decode(raw_msg)

            # Parse the MIME message
            parser = BytesParser(policy=policy.default)
            mime_msg = parser.parsebytes(msg_bytes)

            # Extract message metadata from Gmail
            gmail_id = gmail_message.get("id")
            thread_id = gmail_message.get("threadId")
            headers = {
                h["name"]: h["value"]
                for h in gmail_message.get("payload", {}).get("headers", [])
            }

            # Use our common MIME parsing utility
            parsed = parse_mime_message(mime_msg)

            # Create attachments if present
            attachments = []
            if parsed.get("attachments"):
                for attachment_data in parsed["attachments"]:
                    # Create attachment record
                    attachment = Attachment(
                        name=attachment_data["filename"],
                        content_type=attachment_data["content_type"],
                        size=len(attachment_data["content"]),
                    )

                    # Set content file
                    content = ContentFile(attachment_data["content"])
                    attachment.file.save(
                        attachment_data["filename"], content, save=False,
                    )
                    attachments.append(attachment)

            # Build result
            return {
                "message_id": parsed.get("message_id") or gmail_id,
                "external_id": gmail_id,
                "thread_id": thread_id,
                "subject": parsed.get("subject", "(No subject)"),
                "from_email": parsed.get("from_email"),
                "to_emails": parsed.get("to_emails", []),
                "cc_emails": parsed.get("cc_emails", []),
                "bcc_emails": parsed.get("bcc_emails", []),
                "date": parsed.get("date"),
                "text": parsed.get("text", ""),
                "html": parsed.get("html", ""),
                "attachments": attachments,
                "headers": headers,
                "source": "gmail_api",
            }

        except Exception as e:
            logger.warning(f"Failed to parse Gmail message: {e!s}")
            return None

    def delete_message(self, message_id: str) -> bool:
        """Move a message to trash in Gmail.

        Args:
        ----
            message_id: The message ID to delete

        Returns:
        -------
            True if successful, False otherwise

        """
        if not self.service:
            self.connect()

        try:
            # Move the message to trash rather than permanent deletion
            self.service.users().messages().trash(userId="me", id=message_id).execute()

            logger.info(f"Moved message {message_id} to trash")
            return True

        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e!s}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the Gmail API.

        For API-based connections, we simply nullify the service.
        """
        self.service = None
        self.credentials = None
        logger.debug("Disconnected from Gmail API")

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str | None = None) -> str:
        """Get the OAuth2 authorization URL for Gmail.

        Args:
        ----
            redirect_uri: URI to redirect to after auth
            state: Optional state parameter for security

        Returns:
        -------
            Authorization URL to redirect the user to

        """
        client_id = get_config("GMAIL_CLIENT_ID")
        client_secret = get_config("GMAIL_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ConfigurationError("Missing Gmail OAuth client configuration")

        # Create the OAuth2 flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                },
            },
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
            ],
            state=state,
        )

        flow.redirect_uri = redirect_uri

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline", prompt="consent", include_granted_scopes="true",
        )

        return auth_url

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for OAuth tokens.

        Args:
        ----
            code: Authorization code from OAuth2 redirect
            redirect_uri: Redirect URI used in authorization

        Returns:
        -------
            Dictionary with token information

        Raises:
        ------
            AuthenticationError: If token exchange fails

        """
        client_id = get_config("GMAIL_CLIENT_ID")
        client_secret = get_config("GMAIL_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ConfigurationError("Missing Gmail OAuth client configuration")

        try:
            # Create the OAuth2 flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri],
                    },
                },
                scopes=[
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.send",
                ],
            )

            flow.redirect_uri = redirect_uri

            # Exchange code for tokens
            flow.fetch_token(code=code)

            # Get credentials and extract tokens
            credentials = flow.credentials

            return {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": (
                    credentials.expiry.isoformat() if credentials.expiry else None
                ),
            }

        except Exception as e:
            error_msg = f"Failed to exchange OAuth2 code: {e!s}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)
