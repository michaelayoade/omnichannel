"""Message service for email integration.

This module handles all operations related to email messages:
- Sending outbound messages
- Replying to and forwarding emails
- Message retrieval and querying
"""

import uuid

from django.db import transaction
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger, with_request_id

from ..channels.adapters.factory import get_adapter
from ..enums import MessageDirection, MessageStatus
from ..exceptions import MessageNotFoundError, SendError
from ..models import EmailMessage
from .base_service import BaseService

logger = ContextLogger(__name__)


class MessageService(BaseService):
    """Service for managing email messages."""

    @transaction.atomic
    @with_request_id
    def send_message(self, account_id, message_data, _request_id=None):
        """Send a new email message.

        Args:
        ----
            account_id: ID of the account to send from
            message_data: Dictionary with message data
            _request_id: Optional request ID for logging

        Returns:
        -------
            Sent EmailMessage instance

        Raises:
        ------
            AccountNotFoundError: If account doesn't exist
            SendError: If sending fails

        """
        # Set context for logging
        logger.set_context(
            request_id=_request_id, account_id=account_id, action="send_message",
        )

        account = self.get_account(account_id)

        try:
            # Generate unique message ID if not provided
            if not message_data.get("message_id"):
                message_data["message_id"] = (
                    f"<{uuid.uuid4()}@{account.email_address.split('@')[1]}>"
                )

            # Create message record first
            message = EmailMessage(
                account=account,
                message_id=message_data["message_id"],
                conversation_id=message_data.get(
                    "conversation_id", message_data["message_id"],
                ),
                subject=message_data.get("subject", ""),
                sender=account.email_address,
                recipient=message_data.get("recipient", ""),
                cc=message_data.get("cc", ""),
                body=message_data.get("body", ""),
                sent_at=timezone.now(),
                status=MessageStatus.PENDING,
                direction=MessageDirection.OUTBOUND,
                attachments=message_data.get("attachments", []),
            )
            message.save()

            # Get appropriate adapter for sending
            adapter = get_adapter(account)

            # Authenticate and send message
            adapter.authenticate()
            send_result = adapter.send_message(message_data)

            # Update message status
            message.status = MessageStatus.SENT
            message.save(update_fields=["status", "updated_at"])

            logger.info(
                "Message sent successfully",
                extra={"message_id": message.id, "recipient": message.recipient},
            )

            return message

        except Exception as e:
            if "message" in locals():
                # Update message status to failed
                message.status = MessageStatus.FAILED
                message.error_message = str(e)
                message.save(update_fields=["status", "error_message", "updated_at"])

            logger.error("Failed to send message", extra={"error": str(e)})
            raise SendError(f"Failed to send message: {e!s}")

    @transaction.atomic
    def reply_to_message(self, original_message_id, reply_data):
        """Reply to an existing email message.

        Args:
        ----
            original_message_id: ID of the message to reply to
            reply_data: Dictionary with reply data

        Returns:
        -------
            Sent EmailMessage instance

        Raises:
        ------
            MessageNotFoundError: If original message doesn't exist
            SendError: If sending fails

        """
        try:
            # Get the original message
            original = EmailMessage.objects.select_related("account").get(
                id=original_message_id,
            )
        except EmailMessage.DoesNotExist:
            raise MessageNotFoundError(
                f"Message with ID {original_message_id} not found",
            )

        # Set up reply data
        if not reply_data.get("subject"):
            # Add Re: prefix if not already present
            subject = original.subject
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
            reply_data["subject"] = subject

        # Set recipient as the original sender
        if not reply_data.get("recipient"):
            reply_data["recipient"] = original.sender

        # Set conversation ID to match original message
        reply_data["conversation_id"] = original.conversation_id

        # Set in-reply-to header if using advanced headers
        if not reply_data.get("headers"):
            reply_data["headers"] = {}
        reply_data["headers"]["In-Reply-To"] = original.message_id

        # Send the reply
        return self.send_message(original.account.id, reply_data)

    @transaction.atomic
    def forward_message(self, original_message_id, forward_data):
        """Forward an existing email message.

        Args:
        ----
            original_message_id: ID of the message to forward
            forward_data: Dictionary with forward data

        Returns:
        -------
            Sent EmailMessage instance

        Raises:
        ------
            MessageNotFoundError: If original message doesn't exist
            SendError: If sending fails

        """
        try:
            # Get the original message
            original = EmailMessage.objects.select_related("account").get(
                id=original_message_id,
            )
        except EmailMessage.DoesNotExist:
            raise MessageNotFoundError(
                f"Message with ID {original_message_id} not found",
            )

        # Set up forward data
        if not forward_data.get("subject"):
            # Add Fwd: prefix if not already present
            subject = original.subject
            if not subject.lower().startswith("fwd:"):
                subject = f"Fwd: {subject}"
            forward_data["subject"] = subject

        # Include original message body if not specified
        if not forward_data.get("body"):
            forward_data["body"] = self._create_forward_body(original)

        # Include original attachments if not specified
        if not forward_data.get("attachments") and original.attachments:
            forward_data["attachments"] = original.attachments

        # Send the forward
        return self.send_message(original.account.id, forward_data)

    def get_message_by_id(self, message_id):
        """Get a message by ID.

        Args:
        ----
            message_id: ID of the message to retrieve

        Returns:
        -------
            EmailMessage instance

        Raises:
        ------
            MessageNotFoundError: If message doesn't exist

        """
        try:
            return EmailMessage.objects.select_related("account").get(id=message_id)
        except EmailMessage.DoesNotExist:
            raise MessageNotFoundError(f"Message with ID {message_id} not found")

    def list_messages(
        self,
        account_id=None,
        status=None,
        direction=None,
        conversation_id=None,
        limit=100,
        offset=0,
    ):
        """List email messages with optional filtering.

        Args:
        ----
            account_id: Optional account ID to filter by
            status: Optional message status to filter by
            direction: Optional message direction to filter by
            conversation_id: Optional conversation ID to filter by
            limit: Maximum number of messages to return
            offset: Offset for pagination

        Returns:
        -------
            QuerySet of EmailMessage instances

        """
        # Start with all messages
        queryset = EmailMessage.objects.select_related("account")

        # Apply filters
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        if status:
            queryset = queryset.filter(status=status)

        if direction:
            queryset = queryset.filter(direction=direction)

        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)

        # Order by received/sent date and apply pagination
        return queryset.order_by("-received_at", "-sent_at")[offset : offset + limit]

    def _create_forward_body(self, original_message):
        """Create a body for a forwarded message.

        Args:
        ----
            original_message: Original EmailMessage instance

        Returns:
        -------
            Formatted forward body text

        """
        # Format the original message as a forward
        forward_body = "\n\n---------- Forwarded message ---------\n"
        forward_body += f"From: {original_message.sender}\n"
        forward_body += (
            f"Date: {original_message.received_at.strftime('%a, %d %b %Y %H:%M:%S')}\n"
        )
        forward_body += f"Subject: {original_message.subject}\n"
        forward_body += f"To: {original_message.recipient}\n\n"
        forward_body += original_message.body

        return forward_body


# Convenience functions that use the service
def send_message(account_id, message_data, request=None):
    """Send a new email message."""
    service = MessageService(request)
    return service.send_message(account_id, message_data)


def reply_to_message(original_message_id, reply_data, request=None):
    """Reply to an existing email message."""
    service = MessageService(request)
    return service.reply_to_message(original_message_id, reply_data)


def forward_message(original_message_id, forward_data, request=None):
    """Forward an existing email message."""
    service = MessageService(request)
    return service.forward_message(original_message_id, forward_data)


def get_message_by_id(message_id, request=None):
    """Get a message by ID."""
    service = MessageService(request)
    return service.get_message_by_id(message_id)


def list_messages(
    account_id=None,
    status=None,
    direction=None,
    conversation_id=None,
    limit=100,
    offset=0,
    request=None,
):
    """List email messages with optional filtering."""
    service = MessageService(request)
    return service.list_messages(
        account_id, status, direction, conversation_id, limit, offset,
    )
