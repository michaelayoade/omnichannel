import email
import imaplib
import logging
import poplib
from typing import Dict, List, Tuple

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from email_integration.channels.adapters.base import BaseInboundAdapter
from email_integration.exceptions import (
    AuthenticationError,
    ConnectionError,
    PollingError,
)
from email_integration.models import (
    EmailAccount,
    EmailAttachment,
    EmailContact,
    EmailMessage,
    EmailPollLog,
    EmailThread,
)
from email_integration.utils.email_parser import EmailParser, EmailThreadParser

logger = logging.getLogger(__name__)


class IMAPService(BaseInboundAdapter):
    """
    IMAP service for receiving emails from email accounts.
    Supports both IMAP and POP3 protocols with polling mechanism.
    """

    def __init__(self, email_account: EmailAccount):
        super().__init__(email_account)
        self.account = email_account
        self.parser = EmailParser()
        self.thread_parser = EmailThreadParser()

    def _create_imap_connection(self) -> imaplib.IMAP4:
        """Create IMAP connection."""
        try:
            if self.account.incoming_use_ssl:
                imap = imaplib.IMAP4_SSL(
                    self.account.incoming_server, self.account.incoming_port
                )
            else:
                imap = imaplib.IMAP4(
                    self.account.incoming_server, self.account.incoming_port
                )

            imap.login(self.account.incoming_username, self.account.incoming_password)
            return imap

        except imaplib.IMAP4.error as e:
            if "authentication failed" in str(e).lower():
                raise AuthenticationError(f"IMAP authentication failed: {e}")
            raise ConnectionError(f"IMAP connection failed: {e}")
        except Exception as e:
            raise ConnectionError(
                f"A unexpected error occurred during IMAP connection: {e}"
            )

    def _create_pop3_connection(self) -> poplib.POP3:
        """Create POP3 connection."""
        try:
            if self.account.incoming_use_ssl:
                pop = poplib.POP3_SSL(
                    self.account.incoming_server, self.account.incoming_port
                )
            else:
                pop = poplib.POP3(
                    self.account.incoming_server, self.account.incoming_port
                )

            pop.user(self.account.incoming_username)
            pop.pass_(self.account.incoming_password)
            return pop

        except poplib.error_proto as e:
            if "authentication failed" in str(e).lower():
                raise AuthenticationError(f"POP3 authentication failed: {e}")
            raise ConnectionError(f"POP3 connection failed: {e}")
        except Exception as e:
            raise ConnectionError(
                f"A unexpected error occurred during POP3 connection: {e}"
            )

    def validate_credentials(self) -> bool:
        """Validate IMAP/POP3 credentials by connecting and logging in."""
        try:
            if self.account.incoming_protocol == "imap":
                with self._create_imap_connection():
                    pass  # Connection successful
            else:
                with self._create_pop3_connection():
                    pass  # Connection successful
            return True
        except (AuthenticationError, ConnectionError) as e:
            logger.warning(
                f"Credential validation failed for account {self.account_id}: {e}"
            )
            return False

    def poll(self, max_emails: int = None) -> EmailPollLog:
        """
        Poll for new emails using configured protocol.

        Args:
            max_emails: Maximum number of emails to process (None = use account setting)

        Returns:
            EmailPollLog object with polling results
        """
        started_at = timezone.now()
        max_emails = max_emails or self.account.max_emails_per_poll

        poll_log = EmailPollLog.objects.create(
            account=self.account, status="success", started_at=started_at
        )

        try:
            if self.account.incoming_protocol == "imap":
                self._poll_imap_emails(poll_log, max_emails)
            else:
                self._poll_pop3_emails(poll_log, max_emails)

            # Update account statistics
            self.account.last_poll_at = timezone.now()
            self.account.last_successful_poll_at = timezone.now()
            self.account.last_error_message = ""
            self.account.total_emails_received += poll_log.messages_processed
            self.account.save()

            poll_log.completed_at = timezone.now()
            poll_log.poll_duration = (
                poll_log.completed_at - poll_log.started_at
            ).total_seconds()
            poll_log.save()

            logger.info(
                f"Email poll completed for {self.account.email_address}: "
                f"{poll_log.messages_processed} processed, {poll_log.messages_failed} failed"
            )

            return poll_log

        except (AuthenticationError, ConnectionError, PollingError) as e:
            poll_log.status = "error"
            poll_log.error_message = str(e)
            poll_log.completed_at = timezone.now()
            poll_log.save()

            # Update account error status
            self.account.last_poll_at = timezone.now()
            self.account.last_error_message = str(e)
            self.account.save()

            logger.error(
                f"Email poll for {self.account.email_address} failed due to a channel error: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during email poll for {self.account.email_address}: {e}"
            )
            raise PollingError(
                f"An unexpected error occurred during email poll: {e}"
            ) from e

    def _poll_imap_emails(self, poll_log: EmailPollLog, max_emails: int):
        """Poll emails using IMAP protocol."""
        with self._create_imap_connection() as imap:
            # Select INBOX
            imap.select("INBOX")

            # Search for unread emails
            _, message_numbers = imap.search(None, "UNSEEN")

            if not message_numbers[0]:
                poll_log.status = "no_messages"
                return

            message_ids = message_numbers[0].split()
            poll_log.messages_found = len(message_ids)

            # Limit number of messages to process
            if max_emails and len(message_ids) > max_emails:
                message_ids = message_ids[-max_emails:]

            for msg_id in message_ids:
                try:
                    # Fetch email
                    _, msg_data = imap.fetch(msg_id, "(RFC822)")
                    email_message = email.message_from_bytes(msg_data[0][1])

                    # Process email
                    self._process_email_message(email_message, poll_log)
                    poll_log.messages_processed += 1

                except Exception as e:
                    logger.error(f"Error processing IMAP message {msg_id}: {e}")
                    poll_log.messages_failed += 1
                    # Optionally, re-raise as a PollingError if you want to stop the whole poll
                    # raise PollingError(f"Failed to process message {msg_id}") from e

            poll_log.save()

    def _poll_pop3_emails(self, poll_log: EmailPollLog, max_emails: int):
        """Poll emails using POP3 protocol."""
        with self._create_pop3_connection() as pop:
            # Get message count
            num_messages = len(pop.list()[1])
            poll_log.messages_found = num_messages

            if num_messages == 0:
                poll_log.status = "no_messages"
                return

            # Limit number of messages to process
            start_msg = max(1, num_messages - max_emails + 1) if max_emails else 1

            for msg_num in range(start_msg, num_messages + 1):
                try:
                    # Fetch email
                    lines = pop.retr(msg_num)[1]
                    email_content = b"\n".join(lines)
                    email_message = email.message_from_bytes(email_content)

                    # Check if message already exists (by Message-ID)
                    message_id = email_message.get("Message-ID", "").strip("<>")
                    if (
                        message_id
                        and EmailMessage.objects.filter(
                            external_message_id=message_id
                        ).exists()
                    ):
                        continue

                    # Process email
                    self._process_email_message(email_message, poll_log)
                    poll_log.messages_processed += 1

                    # Delete message from server (POP3 behavior)
                    # pop.dele(msg_num)

                except Exception as e:
                    logger.error(f"Error processing POP3 message {msg_num}: {e}")
                    poll_log.messages_failed += 1

            poll_log.save()

    def _process_email_message(
        self, email_message: email.message.Message, poll_log: EmailPollLog
    ):
        """Process a single email message and save to database."""

        try:
            # Parse email headers and content
            parsed_data = self.parser.parse_email(email_message)

            # Check if message already exists
            message_id = parsed_data.get("message_id", "")
            if (
                message_id
                and EmailMessage.objects.filter(external_message_id=message_id).exists()
            ):
                logger.debug(f"Message {message_id} already exists, skipping")
                return

            # Generate internal message ID and thread ID
            internal_message_id = self.parser.generate_message_id()
            thread_id = self.thread_parser.generate_thread_id(
                parsed_data.get("subject", ""),
                parsed_data.get("in_reply_to", ""),
                parsed_data.get("references", ""),
            )

            with transaction.atomic():
                # Create email message
                email_msg = EmailMessage.objects.create(
                    account=self.account,
                    message_id=internal_message_id,
                    external_message_id=message_id,
                    thread_id=thread_id,
                    direction="inbound",
                    status="received",
                    priority=self._determine_priority(parsed_data),
                    from_email=parsed_data.get("from_email", ""),
                    from_name=parsed_data.get("from_name", ""),
                    to_emails=parsed_data.get("to_emails", []),
                    cc_emails=parsed_data.get("cc_emails", []),
                    bcc_emails=parsed_data.get("bcc_emails", []),
                    reply_to_email=parsed_data.get("reply_to", ""),
                    subject=parsed_data.get("subject", ""),
                    plain_body=parsed_data.get("plain_body", ""),
                    html_body=parsed_data.get("html_body", ""),
                    in_reply_to=parsed_data.get("in_reply_to", ""),
                    references=parsed_data.get("references", ""),
                    raw_headers=parsed_data.get("headers", {}),
                    raw_message=email_message.as_string(),
                    received_at=parsed_data.get("date", timezone.now()),
                )

                # Process attachments
                if parsed_data.get("attachments"):
                    self._process_attachments(email_msg, parsed_data["attachments"])

                # Create or update contact
                self._create_or_update_contact(email_msg)

                # Update or create thread
                self._update_email_thread(email_msg)

                # Link to customer if possible
                self._link_to_customer(email_msg)

                logger.debug(f"Processed email: {email_msg.subject}")

        except Exception as e:
            logger.error(f"Error processing email message: {e}")
            raise

    def _process_attachments(
        self, email_message: EmailMessage, attachments: List[Dict]
    ):
        """Process and save email attachments."""
        for attachment_data in attachments:
            try:
                # Create attachment record
                attachment = EmailAttachment.objects.create(
                    message=email_message,
                    filename=attachment_data["filename"],
                    content_type=attachment_data["content_type"],
                    content_id=attachment_data.get("content_id", ""),
                    size=len(attachment_data["content"]),
                    is_inline=attachment_data.get("is_inline", False),
                )

                # Save file content
                file_content = ContentFile(
                    attachment_data["content"], name=attachment_data["filename"]
                )
                attachment.file_path.save(attachment_data["filename"], file_content)

            except Exception as e:
                logger.error(
                    f"Error processing attachment {attachment_data['filename']}: {e}"
                )

    def _create_or_update_contact(self, email_message: EmailMessage):
        """Create or update email contact."""
        try:
            # Parse sender information
            from_name = email_message.from_name
            from_email = email_message.from_email

            if not from_email:
                return

            # Get or create contact
            contact, created = EmailContact.objects.get_or_create(
                account=self.account,
                email_address=from_email,
                defaults={
                    "display_name": from_name,
                    "last_email_at": email_message.received_at,
                },
            )

            if not created:
                # Update existing contact
                if from_name and not contact.display_name:
                    contact.display_name = from_name

                contact.total_emails_received += 1
                contact.last_email_at = email_message.received_at
                contact.save()

            # Try to parse name into first/last
            if from_name and not contact.first_name:
                name_parts = from_name.split()
                if len(name_parts) >= 2:
                    contact.first_name = name_parts[0]
                    contact.last_name = " ".join(name_parts[1:])
                    contact.save()

        except Exception as e:
            logger.error(f"Error creating/updating contact for {from_email}: {e}")

    def _update_email_thread(self, email_message: EmailMessage):
        """Update or create email thread."""
        try:
            if not email_message.thread_id:
                return

            # Get or create thread
            thread, created = EmailThread.objects.get_or_create(
                thread_id=email_message.thread_id,
                defaults={
                    "account": self.account,
                    "subject": email_message.subject,
                    "participants": [email_message.from_email],
                    "message_count": 1,
                    "first_message_at": email_message.received_at,
                    "last_message_at": email_message.received_at,
                },
            )

            if not created:
                # Update existing thread
                thread.message_count += 1
                thread.last_message_at = email_message.received_at

                # Add participant if not already in list
                if email_message.from_email not in thread.participants:
                    thread.participants.append(email_message.from_email)

                thread.save()

        except Exception as e:
            logger.error(f"Error updating thread {email_message.thread_id}: {e}")

    def _link_to_customer(self, email_message: EmailMessage):
        """Try to link email message to existing customer."""
        try:
            from customers.models import Customer

            # Try to find customer by email
            customer = Customer.objects.filter(email=email_message.from_email).first()

            if customer:
                email_message.linked_customer = customer
                email_message.save()

                # Also link the thread
                if email_message.thread_id:
                    thread = EmailThread.objects.filter(
                        thread_id=email_message.thread_id
                    ).first()
                    if thread and not thread.linked_customer:
                        thread.linked_customer = customer
                        thread.save()

        except Exception as e:
            logger.error(f"Error linking email to customer: {e}")

    def _determine_priority(self, parsed_data: Dict) -> str:
        """Determine email priority from headers."""
        headers = parsed_data.get("headers", {})

        # Check X-Priority header
        x_priority = headers.get("X-Priority", "").lower()
        if x_priority in ["1", "high"]:
            return "high"
        elif x_priority in ["5", "low"]:
            return "low"

        # Check Importance header
        importance = headers.get("Importance", "").lower()
        if importance == "high":
            return "high"
        elif importance == "low":
            return "low"

        # Check for urgent keywords in subject
        subject = parsed_data.get("subject", "").lower()
        urgent_keywords = ["urgent", "emergency", "asap", "critical"]
        if any(keyword in subject for keyword in urgent_keywords):
            return "urgent"

        return "normal"

    def test_connection(self) -> Tuple[bool, str]:
        """Test email connection and authentication."""
        try:
            if self.account.incoming_protocol == "imap":
                with self._create_imap_connection() as imap:
                    imap.select("INBOX")
                    return True, "IMAP connection successful"
            else:
                with self._create_pop3_connection() as pop:
                    pop.stat()
                    return True, "POP3 connection successful"

        except EmailReceiveError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_folder_list(self) -> List[str]:
        """Get list of available IMAP folders."""
        if self.account.incoming_protocol != "imap":
            return ["INBOX"]

        try:
            with self._create_imap_connection() as imap:
                _, folders = imap.list()
                folder_names = []

                for folder in folders:
                    # Parse folder name from IMAP LIST response
                    parts = folder.decode().split('"')
                    if len(parts) >= 3:
                        folder_names.append(parts[-2])

                return folder_names

        except Exception as e:
            logger.error(f"Error getting folder list: {e}")
            return ["INBOX"]

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read on the server (IMAP only)."""
        if self.account.incoming_protocol != "imap":
            return False

        try:
            with self._create_imap_connection() as imap:
                imap.select("INBOX")

                # Search for message by Message-ID
                _, msg_nums = imap.search(None, f'HEADER Message-ID "{message_id}"')

                if msg_nums[0]:
                    msg_num = msg_nums[0].split()[0]
                    imap.store(msg_num, "+FLAGS", "\\Seen")
                    return True

        except Exception as e:
            logger.error(f"Error marking message as read: {e}")

        return False
