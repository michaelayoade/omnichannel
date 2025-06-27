"""
SMTP email protocol adapter implementation.

This module provides an SMTP adapter for sending outbound email messages
with support for plain text, HTML content, and attachments.
"""

import smtplib
import socket
import ssl
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any, Dict, List

from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger

from ...config import get_config
from ...exceptions import AuthenticationError, ConnectionError, SendError
from ..adapters.base import BaseOutboundAdapter
from ..utils import parse_email_address, sanitize_html

logger = ContextLogger(__name__)


class SMTPAdapter(BaseOutboundAdapter):
    """
    SMTP adapter for sending email messages.

    Handles connection to SMTP servers, authentication, and message sending
    with support for plain text, HTML content, and attachments.
    """

    def __init__(self, account):
        """
        Initialize the SMTP adapter with an email account.

        Args:
            account: The EmailAccount model instance
        """
        self.account = account
        self.server = None
        self.use_tls = account.smtp_use_tls
        self.use_ssl = account.smtp_use_ssl
        self.connection_timeout = get_config("DEFAULT_TIMEOUT", 30)
        self.request_id = str(uuid.uuid4())

        # Set up logging context
        logger.set_context(
            account_id=account.id,
            adapter="SMTPAdapter",
            email_address=account.email_address,
            request_id=self.request_id,
        )

    def connect(self) -> None:
        """
        Establish a connection to the SMTP server.

        Raises:
            ConnectionError: If unable to connect to the server
        """
        try:
            logger.info(
                "Connecting to SMTP server",
                extra={
                    "server": self.account.smtp_server,
                    "port": self.account.smtp_port,
                    "use_tls": self.use_tls,
                    "use_ssl": self.use_ssl,
                },
            )

            # Create the appropriate server based on SSL settings
            if self.use_ssl:
                self.server = smtplib.SMTP_SSL(
                    host=self.account.smtp_server,
                    port=self.account.smtp_port,
                    timeout=self.connection_timeout,
                )
            else:
                self.server = smtplib.SMTP(
                    host=self.account.smtp_server,
                    port=self.account.smtp_port,
                    timeout=self.connection_timeout,
                )

                # Use TLS if required
                if self.use_tls:
                    self.server.starttls()

            logger.debug("Connected to SMTP server")

        except (socket.error, ssl.SSLError, smtplib.SMTPException) as e:
            error_msg = f"Failed to connect to SMTP server: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    def authenticate(self) -> None:
        """
        Authenticate to the SMTP server using account credentials.

        Raises:
            AuthenticationError: If authentication fails
        """
        if not self.server:
            self.connect()

        try:
            credentials = self.account.get_credentials()
            username = credentials["smtp"]["username"]
            password = credentials["smtp"]["password"]

            logger.info("Authenticating to SMTP server")

            # Authenticate to the server
            self.server.login(username, password)

            # If we get here, authentication succeeded
            logger.debug("SMTP authentication successful")

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

        except Exception as e:
            # Catch any unexpected errors
            error_msg = f"Unexpected error during SMTP authentication: {str(e)}"
            logger.exception(error_msg)
            raise AuthenticationError(error_msg)

    def send(
        self,
        to_emails: List[str],
        subject: str,
        plain_body: str = None,
        html_body: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send an email message through the SMTP server.

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            plain_body: Plain text content (required if html_body not provided)
            html_body: HTML content (optional)
            **kwargs: Additional parameters:
                cc: Carbon copy recipients (list)
                bcc: Blind carbon copy recipients (list)
                attachments: List of attachment objects with name, content, content_type
                reply_to: Reply-to email address
                from_name: Sender display name

        Returns:
            Dictionary with message details including message_id

        Raises:
            SendError: If there is an error sending the message
            ValueError: If neither plain_body nor html_body is provided
        """
        if not plain_body and not html_body:
            error_msg = "Either plain_body or html_body must be provided"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Make sure we're connected and authenticated
            if not self.server:
                self.connect()
                self.authenticate()

            # Create a message container
            msg = MIMEMultipart("alternative")

            # Extract optional parameters
            cc = kwargs.get("cc", [])
            bcc = kwargs.get("bcc", [])
            attachments = kwargs.get("attachments", [])
            reply_to = kwargs.get("reply_to")
            from_name = kwargs.get(
                "from_name", self.account.display_name or self.account.name
            )

            # Set basic headers
            msg["Subject"] = subject
            msg["From"] = parse_email_address(self.account.email_address, from_name)
            msg["To"] = ", ".join(to_emails)
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(
                domain=self.account.email_address.split("@")[1]
            )

            # Set additional headers if provided
            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to

            # Attach text part
            if plain_body:
                msg.attach(MIMEText(plain_body, "plain"))

            # Attach HTML part
            if html_body:
                # Sanitize HTML to prevent XSS
                sanitized_html = sanitize_html(html_body)
                msg.attach(MIMEText(sanitized_html, "html"))

            # Add attachments if present
            for attachment in attachments:
                filename = attachment["name"]
                content = attachment["content"]
                content_type = attachment.get(
                    "content_type", "application/octet-stream"
                )

                # Create attachment part
                part = MIMEApplication(content)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                part.add_header("Content-Type", content_type)
                msg.attach(part)

            # Combine all recipients
            all_recipients = to_emails + cc + bcc

            # Send the message
            logger.info(f"Sending email to {len(all_recipients)} recipients")
            self.server.send_message(
                msg, from_addr=self.account.email_address, to_addrs=all_recipients
            )

            # Log success
            logger.info(
                "Email sent successfully",
                extra={
                    "message_id": msg["Message-ID"],
                    "recipients": len(all_recipients),
                },
            )

            # Return message details
            return {
                "message_id": msg["Message-ID"],
                "subject": subject,
                "recipients": all_recipients,
                "sent_at": timezone.now().isoformat(),
            }

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error sending message: {str(e)}"
            logger.error(error_msg)
            raise SendError(error_msg)

        except (socket.error, ssl.SSLError) as e:
            error_msg = f"Connection error sending message: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error sending message: {str(e)}"
            logger.exception(error_msg)
            raise SendError(error_msg)

        finally:
            # Always close the connection after sending
            self.disconnect()

    def disconnect(self) -> None:
        """
        Close the connection to the SMTP server.
        """
        if self.server:
            try:
                self.server.quit()
                logger.debug("Disconnected from SMTP server")
            except (smtplib.SMTPException, socket.error) as e:
                logger.warning(f"Error disconnecting from SMTP server: {str(e)}")
            finally:
                self.server = None
