"""
IMAP adapter implementation for email integration.

This module provides adapter classes for connecting to and interacting
with email accounts using the Internet Message Access Protocol (IMAP).
"""

import email
import imaplib
import re
import ssl
from datetime import timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger

from ... import config
from ...exceptions import AuthenticationError, ConnectionError
from ...models import EmailAccount
from .. import utils
from .base import BaseAdapter, BaseInboundAdapter

logger = ContextLogger(__name__)


class IMAPAdapter(BaseAdapter, BaseInboundAdapter):
    """
    IMAP protocol adapter for email integration.

    This adapter implements the BaseInboundAdapter interface for the
    IMAP protocol, allowing polling and retrieval of email messages.
    """

    def __init__(self, account: EmailAccount):
        """
        Initialize IMAP adapter with account settings.

        Args:
            account: EmailAccount instance with IMAP server settings
        """
        super().__init__(account)
        self.server = None
        self.settings = account.server_settings or {}
        self.server_host = self.settings.get("imap_server")
        self.server_port = self.settings.get("imap_port", 993)
        self.use_ssl = self.settings.get("use_ssl", True)
        self.timeout = self.settings.get("timeout", config.DEFAULT_TIMEOUT)
        self.username = account.username
        # Password should be decrypted if encryption is used
        self.password = (
            account.password
        )  # In production, use a proper encryption/decryption mechanism

    def authenticate(self):
        """
        Establish connection and authenticate with the IMAP server.

        Returns:
            True if authentication was successful

        Raises:
            ConnectionError: If connection to server fails
            AuthenticationError: If authentication fails
        """
        logger.info(
            "Connecting to IMAP server",
            extra={"account_id": self.account.id, "server": self.server_host},
        )

        try:
            # Create the appropriate connection based on settings
            if self.use_ssl:
                self.server = imaplib.IMAP4_SSL(
                    self.server_host,
                    self.server_port,
                    timeout=self.timeout,
                    ssl_context=self._create_ssl_context(),
                )
            else:
                self.server = imaplib.IMAP4(
                    self.server_host, self.server_port, timeout=self.timeout
                )

            # Login to the server
            self.server.login(self.username, self.password)
            logger.info(
                "IMAP authentication successful", extra={"account_id": self.account.id}
            )
            return True

        except imaplib.IMAP4.error as e:
            logger.error(
                "IMAP authentication failed",
                extra={"account_id": self.account.id, "error": str(e)},
            )
            raise AuthenticationError(f"IMAP authentication failed: {str(e)}")

        except (ConnectionRefusedError, TimeoutError, ssl.SSLError, OSError) as e:
            logger.error(
                "IMAP connection failed",
                extra={"account_id": self.account.id, "error": str(e)},
            )
            raise ConnectionError(f"IMAP connection failed: {str(e)}")

    def validate_credentials(self) -> bool:
        """
        Validate account credentials with the IMAP server.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            self.authenticate()
            self._disconnect()
            return True
        except (AuthenticationError, ConnectionError):
            return False

    def fetch_new_messages(self, folder="INBOX", max_messages=None):
        """
        Fetch new messages from the specified IMAP folder.

        Args:
            folder: IMAP folder to check (default: INBOX)
            max_messages: Maximum number of messages to fetch

        Returns:
            List of message data dictionaries

        Raises:
            ConnectionError: If connection to server fails
            AuthenticationError: If authentication fails
        """
        # Ensure we're authenticated
        if not self.server:
            self.authenticate()

        results = []
        max_count = max_messages or config.MAX_MESSAGES_PER_POLL

        try:
            # Select the folder
            status, data = self.server.select(folder)
            if status != "OK":
                logger.warning(
                    "Failed to select folder",
                    extra={"folder": folder, "status": status},
                )
                return results

            # Calculate the date range for filtering
            since_date = timezone.now() - timedelta(days=config.MAX_MESSAGE_AGE_DAYS)
            date_str = since_date.strftime("%d-%b-%Y")

            # Search for unread messages since the date
            search_criteria = f"(SINCE {date_str} UNSEEN)"
            status, data = self.server.search(None, search_criteria)

            if status != "OK":
                logger.warning(
                    "IMAP search failed",
                    extra={"criteria": search_criteria, "status": status},
                )
                return results

            # Get the IDs of all messages that match the criteria
            message_ids = data[0].split()

            # Limit the number of messages
            if max_count and len(message_ids) > max_count:
                message_ids = message_ids[:max_count]

            logger.info(
                f"Found {len(message_ids)} new messages",
                extra={"account_id": self.account.id, "folder": folder},
            )

            # Fetch each message
            for msg_id in message_ids:
                try:
                    message_data = self._fetch_message(msg_id)
                    if message_data:
                        results.append(message_data)
                except Exception as e:
                    logger.error(
                        "Error fetching message",
                        extra={"message_id": msg_id, "error": str(e)},
                    )

            return results

        finally:
            # Ensure we close the connection
            self._disconnect()

    def _fetch_message(self, msg_id):
        """
        Fetch a single message by ID.

        Args:
            msg_id: Message ID to fetch

        Returns:
            Dictionary with message data
        """
        # Fetch the message
        status, msg_data = self.server.fetch(msg_id, "(RFC822)")
        if status != "OK":
            logger.warning(
                "Failed to fetch message",
                extra={"message_id": msg_id, "status": status},
            )
            return None

        # Parse the email message
        email_message = email.message_from_bytes(msg_data[0][1])

        # Extract message details
        message_id = self._get_header(email_message, "Message-ID")
        subject = self._get_header(email_message, "Subject")
        sender = self._get_header(email_message, "From")
        recipient = self._get_header(email_message, "To")
        cc = self._get_header(email_message, "Cc")
        date_str = self._get_header(email_message, "Date")

        # Parse the date
        try:
            received_at = (
                parsedate_to_datetime(date_str) if date_str else timezone.now()
            )
            # Ensure timezone awareness
            if received_at.tzinfo is None:
                received_at = timezone.make_aware(received_at)
        except ValueError:
            received_at = timezone.now()

        # Extract the message body
        body_plain, body_html = self._get_message_body(email_message)

        # Choose HTML if available, otherwise plain text
        body = body_html or body_plain or ""

        # Extract attachments if present
        attachments = self._get_attachments(email_message)

        # Create conversation ID from subject or message ID
        conversation_id = None
        if subject:
            # Remove Re:, Fwd: etc. and trim whitespace
            base_subject = re.sub(
                r"^(?:Re|Fwd|FW|RE):\s*", "", subject, flags=re.IGNORECASE
            )
            if base_subject:
                # Use a hash of the base subject as conversation ID
                conversation_id = utils.hash_string(base_subject)

        # If no conversation ID from subject, use message ID
        if not conversation_id and message_id:
            conversation_id = utils.hash_string(message_id)

        # Fall back to a random value if needed
        if not conversation_id:
            conversation_id = utils.generate_id()

        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "cc": cc,
            "body": body,
            "body_html": body_html,
            "body_plain": body_plain,
            "received_at": received_at,
            "attachments": attachments,
        }

    def _get_header(self, email_message, header_name):
        """
        Extract and decode an email header.

        Args:
            email_message: Email message object
            header_name: Name of header to extract

        Returns:
            Decoded header value or empty string
        """
        value = email_message.get(header_name, "")
        if not value:
            return ""

        # Decode internationalized headers
        decoded_parts = []
        for part, encoding in decode_header(value):
            if isinstance(part, bytes):
                try:
                    decoded_part = part.decode(encoding or "utf-8", errors="replace")
                except (LookupError, TypeError):
                    decoded_part = part.decode("utf-8", errors="replace")
            else:
                decoded_part = str(part)
            decoded_parts.append(decoded_part)

        return "".join(decoded_parts)

    def _get_message_body(self, email_message):
        """
        Extract plain text and HTML bodies from the email message.

        Args:
            email_message: Email message object

        Returns:
            Tuple of (plain_text, html)
        """
        body_plain = None
        body_html = None

        # Handle multipart messages
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()

                if content_type == "text/plain":
                    body_plain = self._decode_part(part)
                elif content_type == "text/html":
                    body_html = self._decode_part(part)

        # Handle simple messages
        else:
            content_type = email_message.get_content_type()
            if content_type == "text/plain":
                body_plain = self._decode_part(email_message)
            elif content_type == "text/html":
                body_html = self._decode_part(email_message)

        return body_plain, body_html

    def _decode_part(self, part):
        """
        Decode the content of an email part.

        Args:
            part: Email message part

        Returns:
            Decoded content as string
        """
        content = part.get_payload(decode=True)
        if content is None:
            return ""

        charset = part.get_content_charset() or "utf-8"
        try:
            return content.decode(charset, errors="replace")
        except LookupError:
            # Fall back to UTF-8 if charset is unknown
            return content.decode("utf-8", errors="replace")

    def _get_attachments(self, email_message):
        """
        Extract attachments from the email message.

        Args:
            email_message: Email message object

        Returns:
            List of attachment dictionaries
        """
        attachments = []

        # Process each part in multipart emails
        for part in email_message.walk():
            # Skip if not an attachment
            if part.get_content_maintype() == "multipart":
                continue

            # Skip if inline content
            if part.get("Content-Disposition") is None:
                continue

            # Skip if not attachment
            if "attachment" not in part.get("Content-Disposition", ""):
                continue

            # Get filename
            filename = part.get_filename()
            if not filename:
                # Generate a filename if none is present
                content_type = part.get_content_type()
                filename = (
                    f"attachment-{len(attachments)+1}.{content_type.split('/')[1]}"
                )

            # Decode filename if needed
            if isinstance(filename, str):
                try:
                    # Handle encoded filenames
                    filename_parts = []
                    for filename_part, encoding in decode_header(filename):
                        if isinstance(filename_part, bytes):
                            filename_part = filename_part.decode(
                                encoding or "utf-8", errors="replace"
                            )
                        filename_parts.append(str(filename_part))
                    filename = "".join(filename_parts)
                except Exception:  # nosec B110
                    # Use as-is if decoding fails
                    pass

            # Get content data
            content = part.get_payload(decode=True)
            size = len(content) if content else 0

            # Check size limit
            if size > config.MAX_ATTACHMENT_SIZE:
                logger.warning(
                    "Attachment exceeds maximum size limit",
                    extra={
                        "filename": filename,
                        "size": size,
                        "limit": config.MAX_ATTACHMENT_SIZE,
                    },
                )
                # Skip this attachment or store metadata only
                attachments.append(
                    {
                        "filename": filename,
                        "content_type": part.get_content_type(),
                        "size": size,
                        "content": None,
                        "truncated": True,
                    }
                )
                continue

            # Add the attachment
            attachments.append(
                {
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "content": utils.encode_attachment(content),
                    "size": size,
                }
            )

        return attachments

    def _create_ssl_context(self):
        """
        Create an SSL context with appropriate security settings.

        Returns:
            Configured SSL context
        """
        context = ssl.create_default_context()

        # Verify certificates by default
        if self.settings.get("verify_ssl", True):
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        return context

    def _disconnect(self):
        """Close the IMAP connection."""
        if self.server:
            try:
                self.server.close()
                self.server.logout()
            except Exception as e:
                logger.warning(
                    "Error disconnecting from IMAP server",
                    extra={"error": str(e), "account_id": self.account.id},
                )
            finally:
                self.server = None
