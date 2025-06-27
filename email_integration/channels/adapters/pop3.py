"""
POP3 email protocol adapter implementation.

This module provides a POP3 adapter that can connect to POP3 email servers
and fetch messages.
"""

import email
import poplib
import socket
import ssl
import uuid
from typing import Any, Dict, List

from omnichannel_core.utils.logging import ContextLogger

from ...config import get_config
from ...exceptions import AuthenticationError, ConnectionError, PollingError
from ..adapters.base import BaseInboundAdapter
from ..utils import (
    create_message_id,
    extract_attachments,
    parse_email_message,
    sanitize_subject,
)

logger = ContextLogger(__name__)


class POP3Adapter(BaseInboundAdapter):
    """
    POP3 adapter for fetching email messages from a POP3 server.

    This adapter handles the connection to the POP3 server,
    authentication, and message fetching.
    """

    def __init__(self, account):
        """
        Initialize the POP3 adapter with an email account.

        Args:
            account: The EmailAccount model instance
        """
        self.account = account
        self.server = None
        self.secure = account.incoming_use_ssl
        self.connection_timeout = get_config("DEFAULT_TIMEOUT", 30)
        self.max_message_age_days = get_config("MAX_MESSAGE_AGE_DAYS", 30)
        self.max_messages_per_poll = min(
            account.max_emails_per_poll, get_config("MAX_MESSAGES_PER_POLL", 50)
        )
        self.request_id = str(uuid.uuid4())

        # Set up logging context
        logger.set_context(
            account_id=account.id,
            adapter="POP3Adapter",
            email_address=account.email_address,
            request_id=self.request_id,
        )

    def connect(self) -> None:
        """
        Establish a connection to the POP3 server.

        Raises:
            ConnectionError: If unable to connect to the server
        """
        try:
            logger.info(
                "Connecting to POP3 server",
                extra={
                    "server": self.account.incoming_server,
                    "port": self.account.incoming_port,
                    "secure": self.secure,
                },
            )

            # Connect to the server
            if self.secure:
                # Use SSL connection
                self.server = poplib.POP3_SSL(
                    host=self.account.incoming_server,
                    port=self.account.incoming_port,
                    timeout=self.connection_timeout,
                )
            else:
                # Use regular connection
                self.server = poplib.POP3(
                    host=self.account.incoming_server,
                    port=self.account.incoming_port,
                    timeout=self.connection_timeout,
                )

            # Get server welcome message
            welcome = self.server.getwelcome().decode("utf-8", errors="replace")
            logger.debug("Connected to POP3 server", extra={"welcome": welcome})

        except (socket.error, ssl.SSLError, poplib.error_proto) as e:
            error_msg = f"Failed to connect to POP3 server: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    def authenticate(self) -> None:
        """
        Authenticate to the POP3 server using account credentials.

        Raises:
            AuthenticationError: If authentication fails
        """
        if not self.server:
            self.connect()

        try:
            credentials = self.account.get_credentials()
            username = credentials["incoming"]["username"]
            password = credentials["incoming"]["password"]

            logger.info("Authenticating to POP3 server")

            # Authenticate to the server
            self.server.user(username)
            self.server.pass_(password)

            # If we get here, authentication succeeded
            logger.debug("POP3 authentication successful")

        except poplib.error_proto as e:
            error_msg = f"POP3 authentication failed: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

        except Exception as e:
            # Catch any unexpected errors
            error_msg = f"Unexpected error during POP3 authentication: {str(e)}"
            logger.exception(error_msg)
            raise AuthenticationError(error_msg)

    def get_new_messages(self) -> List[Dict[str, Any]]:
        """
        Fetch new messages from the POP3 server.

        Returns:
            List of messages as dictionaries with message data

        Raises:
            PollingError: If there is an error fetching messages
        """
        if not self.server:
            self.connect()
            self.authenticate()

        try:
            # Get message count and size
            message_count, mailbox_size = self.server.stat()

            logger.info(f"Total messages in POP3 mailbox: {message_count}")

            if message_count == 0:
                return []

            # Get a list of message IDs and sizes
            messages = self.server.list()[1]

            # Limit the number of messages to fetch
            messages = messages[: self.max_messages_per_poll]

            parsed_messages = []

            # Process each message
            for i, msg_info in enumerate(messages):
                # Parse the message info (msg_id, size)
                msg_data = msg_info.decode("utf-8").split(" ")
                msg_id = msg_data[0]

                logger.debug(
                    f"Fetching message {i+1}/{len(messages)}", extra={"msg_id": msg_id}
                )

                try:
                    # Retrieve the full message
                    response, lines, octets = self.server.retr(msg_id)

                    # Parse the message
                    msg_content = b"\n".join(lines)
                    msg = email.message_from_bytes(msg_content)

                    # Parse email into our format
                    parsed_msg = parse_email_message(msg)

                    # Extract attachments if available
                    attachments = extract_attachments(msg)
                    if attachments:
                        parsed_msg["attachments"] = attachments

                    # Generate a unique message ID if not present
                    if "message_id" not in parsed_msg or not parsed_msg["message_id"]:
                        parsed_msg["message_id"] = create_message_id(
                            parsed_msg["subject"],
                            parsed_msg["sender"],
                            parsed_msg["date"],
                        )

                    # Sanitize the subject
                    parsed_msg["subject"] = sanitize_subject(parsed_msg["subject"])

                    # Add the message to our list
                    parsed_messages.append(parsed_msg)

                except (poplib.error_proto, email.errors.MessageError) as e:
                    # Log error but continue with other messages
                    logger.warning(f"Error processing message {msg_id}: {str(e)}")
                    continue

            logger.info(f"Fetched {len(parsed_messages)} new messages")
            return parsed_messages

        except (poplib.error_proto, socket.error) as e:
            error_msg = f"Error fetching messages from POP3 server: {str(e)}"
            logger.error(error_msg)
            raise PollingError(error_msg)

        finally:
            self.disconnect()

    def disconnect(self) -> None:
        """
        Close the connection to the POP3 server.
        """
        if self.server:
            try:
                self.server.quit()
                logger.debug("Disconnected from POP3 server")
            except (poplib.error_proto, socket.error) as e:
                logger.warning(f"Error disconnecting from POP3 server: {str(e)}")
            finally:
                self.server = None
