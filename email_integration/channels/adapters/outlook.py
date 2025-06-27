"""
Outlook API adapter implementation.

Provides email operations via the Microsoft Graph API for Outlook/Office 365,
supporting OAuth2 authentication, message fetching, and attachment handling.
"""

import base64
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import msal
import requests
from django.core.files.base import ContentFile

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
from ..utils import html_to_text

logger = ContextLogger(__name__)


class OutlookAdapter(BaseInboundAdapter):
    """
    Outlook/Microsoft Graph API adapter for sending and receiving emails.

    Uses OAuth2 authentication to access Microsoft Graph API for email operations.
    Provides functionality to fetch and parse messages from Office 365/Outlook.
    """

    def __init__(self, account):
        """
        Initialize the Outlook adapter with an email account.

        Args:
            account: The EmailAccount model instance
        """
        self.account = account
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self.token = None
        self.max_results = get_config("MAX_MESSAGES_PER_POLL", 20)
        self.connection_timeout = get_config("DEFAULT_TIMEOUT", 30)
        self.request_id = str(uuid.uuid4())

        # Set up logging context
        logger.set_context(
            account_id=account.id,
            adapter="OutlookAdapter",
            email_address=account.email_address,
            request_id=self.request_id,
        )

        # Check if required OAuth2 settings exist
        self._check_oauth2_config()

    def _check_oauth2_config(self) -> None:
        """
        Check if required OAuth2 configuration is available.

        Raises:
            ConfigurationError: If OAuth2 configuration is missing
        """
        settings = self.account.server_settings or {}
        required_keys = ["client_id", "client_secret", "refresh_token"]

        for key in required_keys:
            if key not in settings:
                error_msg = f"Missing required OAuth2 setting: {key}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)

    def _get_credentials(self) -> Dict[str, Any]:
        """
        Get OAuth2 credentials for Microsoft Graph API access.

        Returns:
            Dictionary with credentials for Microsoft Graph API

        Raises:
            AuthenticationError: If credentials cannot be obtained
        """
        try:
            credentials = self.account.get_credentials()
            return credentials.get("oauth2", {})
        except Exception as e:
            error_msg = f"Failed to get OAuth2 credentials: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

    def _get_token(self) -> str:
        """
        Get an access token for Microsoft Graph API.

        Returns:
            Access token string

        Raises:
            AuthenticationError: If token cannot be obtained
        """
        try:
            credentials = self._get_credentials()

            # Try to use existing token if not expired
            if (
                self.token
                and self.token.get("expires_at", 0) > datetime.now().timestamp()
            ):
                return self.token.get("access_token")

            # If we have a refresh token, use it to get a new token
            app = msal.ConfidentialClientApplication(
                client_id=credentials.get("client_id"),
                client_credential=credentials.get("client_secret"),
                authority=f"https://login.microsoftonline.com/{credentials.get('tenant_id', 'common')}",
            )

            result = app.acquire_token_by_refresh_token(
                refresh_token=credentials.get("refresh_token"),
                scopes=[
                    "https://graph.microsoft.com/Mail.Read",
                    "https://graph.microsoft.com/Mail.Send",
                ],
            )

            if "error" in result:
                error_msg = f"Error refreshing token: {result.get('error_description')}"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

            # Store token with expiry
            self.token = {
                "access_token": result.get("access_token"),
                "expires_at": datetime.now().timestamp()
                + result.get("expires_in", 3600),
            }

            return self.token.get("access_token")

        except Exception as e:
            error_msg = f"Failed to get access token: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

    def connect(self) -> None:
        """
        Connect to Microsoft Graph API by obtaining an access token.

        Raises:
            ConnectionError: If connection cannot be established
            AuthenticationError: If authentication fails
        """
        try:
            logger.info("Connecting to Microsoft Graph API")

            # Get an access token
            token = self._get_token()

            # Test connection by getting user profile
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.graph_endpoint}/me",
                headers=headers,
                timeout=self.connection_timeout,
            )

            if response.status_code != 200:
                if response.status_code in (401, 403):
                    error_msg = f"Authentication failed: {response.text}"
                    logger.error(error_msg)
                    raise AuthenticationError(error_msg)
                else:
                    error_msg = (
                        f"Failed to connect to Microsoft Graph API: {response.text}"
                    )
                    logger.error(error_msg)
                    raise ConnectionError(error_msg)

            profile = response.json()
            logger.debug(
                "Connected to Microsoft Graph API",
                extra={"email": profile.get("userPrincipalName")},
            )

        except (AuthenticationError, ConnectionError):
            # Re-raise these specific exceptions
            raise

        except requests.RequestException as e:
            error_msg = f"HTTP error connecting to Microsoft Graph API: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Failed to connect to Microsoft Graph API: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    def authenticate(self) -> None:
        """
        Authenticate to Microsoft Graph API.

        Authenticates by obtaining a valid access token.

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Get a fresh token
            self._get_token()
        except Exception as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

    def fetch_messages(self, since_date=None, limit=None) -> List[Dict[str, Any]]:
        """
        Fetch messages from Outlook/Office 365 via Microsoft Graph API.

        Args:
            since_date: Optional datetime to fetch messages since
            limit: Maximum number of messages to fetch

        Returns:
            List of parsed email message dictionaries

        Raises:
            FetchError: If messages cannot be fetched
        """
        try:
            # Make sure we have a token
            if not self.token:
                self.connect()

            token = self._get_token()

            # Set limit to configured max if not specified
            if not limit or limit > self.max_results:
                limit = self.max_results

            # Build filter for date if provided
            date_filter = ""
            if since_date:
                # Convert to ISO 8601 format
                iso_date = since_date.isoformat()
                date_filter = f"&$filter=receivedDateTime ge {iso_date}"

            # Build request
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Get message list
            url = f"{self.graph_endpoint}/me/messages?$top={limit}{date_filter}"
            response = requests.get(
                url, headers=headers, timeout=self.connection_timeout
            )

            if response.status_code != 200:
                error_msg = f"Failed to fetch messages: {response.text}"
                logger.error(error_msg)
                raise FetchError(error_msg)

            data = response.json()
            messages = data.get("value", [])

            logger.debug(f"Found {len(messages)} messages from Microsoft Graph API")

            # Process messages
            parsed_messages = []
            for msg_data in messages:
                try:
                    parsed_msg = self._parse_outlook_message(msg_data)
                    if parsed_msg:
                        parsed_messages.append(parsed_msg)
                except Exception as e:
                    logger.warning(f"Failed to parse message: {str(e)}")
                    continue

            logger.info(f"Successfully fetched {len(parsed_messages)} messages")
            return parsed_messages

        except (AuthenticationError, ConnectionError, FetchError):
            # Re-raise these specific exceptions
            raise

        except requests.RequestException as e:
            error_msg = f"HTTP error fetching messages: {str(e)}"
            logger.error(error_msg)
            raise FetchError(error_msg)

        except Exception as e:
            error_msg = f"Failed to fetch messages: {str(e)}"
            logger.exception(error_msg)
            raise FetchError(error_msg)

    def _parse_outlook_message(
        self, msg_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an Outlook/Graph API message into our standard format.

        Args:
            msg_data: Message data from Microsoft Graph API

        Returns:
            Dictionary containing parsed email fields or None if parsing failed
        """
        try:
            # Extract basic message info
            message_id = msg_data.get("id")
            subject = msg_data.get("subject", "(No subject)")

            # Parse sender
            sender = msg_data.get("from", {}).get("emailAddress", {})
            from_email = sender.get("address")
            from_name = sender.get("name")

            # Parse recipients
            to_recipients = msg_data.get("toRecipients", [])
            cc_recipients = msg_data.get("ccRecipients", [])
            bcc_recipients = msg_data.get("bccRecipients", [])

            to_emails = [
                r.get("emailAddress", {}).get("address")
                for r in to_recipients
                if r.get("emailAddress", {}).get("address")
            ]
            cc_emails = [
                r.get("emailAddress", {}).get("address")
                for r in cc_recipients
                if r.get("emailAddress", {}).get("address")
            ]
            bcc_emails = [
                r.get("emailAddress", {}).get("address")
                for r in bcc_recipients
                if r.get("emailAddress", {}).get("address")
            ]

            # Get content
            body = msg_data.get("body", {})
            content_type = body.get("contentType", "text")
            content = body.get("content", "")

            # Handle content types
            html_content = content if content_type == "html" else None
            text_content = (
                content
                if content_type == "text"
                else (html_to_text(content) if content_type == "html" else None)
            )

            # Get date
            received_date_str = msg_data.get("receivedDateTime")
            received_date = (
                datetime.fromisoformat(received_date_str.replace("Z", "+00:00"))
                if received_date_str
                else None
            )

            # Handle attachments asynchronously if needed
            attachments = []
            if msg_data.get("hasAttachments", False):
                attachments = self._fetch_attachments(message_id)

            # Build result
            return {
                "message_id": msg_data.get("internetMessageId") or message_id,
                "external_id": message_id,
                "thread_id": msg_data.get("conversationId"),
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name,
                "to_emails": to_emails,
                "cc_emails": cc_emails,
                "bcc_emails": bcc_emails,
                "date": received_date,
                "text": text_content,
                "html": html_content,
                "attachments": attachments,
                "headers": {},  # Graph API doesn't provide raw headers
                "source": "outlook_api",
            }

        except Exception as e:
            logger.warning(f"Failed to parse Outlook message: {str(e)}")
            return None

    def _fetch_attachments(self, message_id: str) -> List[Attachment]:
        """
        Fetch attachments for a message from Microsoft Graph API.

        Args:
            message_id: The message ID

        Returns:
            List of Attachment model instances
        """
        attachments = []

        try:
            token = self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Get attachment list
            url = f"{self.graph_endpoint}/me/messages/{message_id}/attachments"
            response = requests.get(
                url, headers=headers, timeout=self.connection_timeout
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch attachments: {response.text}")
                return []

            data = response.json()
            attachment_data = data.get("value", [])

            for att in attachment_data:
                try:
                    # Skip inline attachments like signatures
                    is_inline = att.get("isInline", False)
                    if is_inline:
                        continue

                    # Create attachment record
                    filename = att.get("name", "unnamed_attachment")
                    content_bytes = None

                    # Handle fileAttachment type
                    if att.get("@odata.type", "") == "#microsoft.graph.fileAttachment":
                        content_b64 = att.get("contentBytes", "")
                        if content_b64:
                            content_bytes = base64.b64decode(content_b64)

                    if content_bytes:
                        attachment = Attachment(
                            name=filename,
                            content_type=att.get(
                                "contentType", "application/octet-stream"
                            ),
                            size=len(content_bytes),
                        )

                        content = ContentFile(content_bytes)
                        attachment.file.save(filename, content, save=False)
                        attachments.append(attachment)

                except Exception as e:
                    logger.warning(f"Failed to process attachment: {str(e)}")
                    continue

        except Exception as e:
            logger.warning(
                f"Failed to fetch attachments for message {message_id}: {str(e)}"
            )

        return attachments

    def delete_message(self, message_id: str) -> bool:
        """
        Delete a message via Microsoft Graph API.

        Args:
            message_id: The message ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            token = self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Delete the message
            url = f"{self.graph_endpoint}/me/messages/{message_id}"
            response = requests.delete(
                url, headers=headers, timeout=self.connection_timeout
            )

            if response.status_code in (204, 200):
                logger.info(f"Successfully deleted message {message_id}")
                return True
            else:
                logger.error(f"Failed to delete message {message_id}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {str(e)}")
            return False

    def disconnect(self) -> None:
        """
        Disconnect from the Microsoft Graph API.

        For API-based connections, we simply invalidate the token.
        """
        self.token = None
        logger.debug("Disconnected from Microsoft Graph API")

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str = None) -> str:
        """
        Get the OAuth2 authorization URL for Microsoft.

        Args:
            redirect_uri: URI to redirect to after auth
            state: Optional state parameter for security

        Returns:
            Authorization URL to redirect the user to
        """
        client_id = get_config("OUTLOOK_CLIENT_ID")
        tenant_id = get_config("OUTLOOK_TENANT_ID", "common")

        if not client_id:
            raise ConfigurationError("Missing Outlook OAuth client configuration")

        # Build Microsoft identity platform authorization URL
        scopes = "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send"
        auth_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scopes}"
            f"&response_mode=query"
        )

        if state:
            auth_url += f"&state={state}"

        return auth_url

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for OAuth tokens.

        Args:
            code: Authorization code from OAuth2 redirect
            redirect_uri: Redirect URI used in authorization

        Returns:
            Dictionary with token information

        Raises:
            AuthenticationError: If token exchange fails
        """
        client_id = get_config("OUTLOOK_CLIENT_ID")
        client_secret = get_config("OUTLOOK_CLIENT_SECRET")
        tenant_id = get_config("OUTLOOK_TENANT_ID", "common")

        if not client_id or not client_secret:
            raise ConfigurationError("Missing Outlook OAuth client configuration")

        try:
            # Exchange code for tokens
            token_url = (
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            )

            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "scope": "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send",
            }

            response = requests.post(token_url, data=data, timeout=30)

            if response.status_code != 200:
                error_msg = f"Failed to exchange code: {response.text}"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

            tokens = response.json()

            # Return tokens
            return {
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "token_type": tokens.get("token_type"),
                "expires_in": tokens.get("expires_in"),
                "scope": tokens.get("scope"),
                "client_id": client_id,
                "client_secret": client_secret,
                "tenant_id": tenant_id,
            }

        except requests.RequestException as e:
            error_msg = f"HTTP error exchanging code: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

        except Exception as e:
            error_msg = f"Failed to exchange OAuth2 code: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)
