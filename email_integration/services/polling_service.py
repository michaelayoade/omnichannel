"""
Polling service for email integration.

This module handles all operations related to polling email accounts:
- Fetching messages from email servers
- Processing incoming messages
- Applying rules and filters
"""

from django.db import transaction
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger, with_request_id

from .. import config
from ..channels.adapters.factory import get_adapter
from ..enums import AccountStatus, MessageDirection, MessageStatus
from ..exceptions import AuthenticationError, ConnectionError
from ..models import EmailAccount, EmailMessage
from .base_service import BaseService

logger = ContextLogger(__name__)


class PollingService(BaseService):
    """Service for polling and processing emails."""

    @with_request_id
    def poll_and_process_account(self, account_id, _request_id=None):
        """
        Poll an email account and process incoming messages.

        Args:
            account_id: ID of the account to poll
            _request_id: Optional request ID for logging

        Returns:
            Dictionary with poll results

        Raises:
            ConnectionError: If connection to email server fails
            AuthenticationError: If authentication fails
        """
        # Set up logging context
        logger.set_context(
            request_id=_request_id, account_id=account_id, action="poll_account"
        )

        start_time = timezone.now()
        logger.info("Starting email account polling")

        try:
            # Get account with optimized query
            account = self.get_account(account_id)

            # Get appropriate adapter for the account
            adapter = get_adapter(account)

            # Connect and authenticate
            try:
                adapter.authenticate()
            except AuthenticationError as e:
                # Update account status on auth failure
                self._update_account_status(account, AccountStatus.AUTH_ERROR)
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "account_id": account_id,
                    "status": "auth_error",
                    "error": str(e),
                }

            # Fetch new messages
            messages = adapter.fetch_new_messages()
            logger.info(f"Fetched {len(messages)} new messages")

            # Process each message
            processed = []
            for message_data in messages:
                try:
                    email_message = self.process_message(account, message_data)
                    processed.append(email_message.id)
                except Exception as e:
                    logger.error(
                        "Error processing message",
                        extra={
                            "message_id": message_data.get("message_id"),
                            "error": str(e),
                        },
                    )

            # Update account status and last poll time
            self._update_account_status(account, AccountStatus.ACTIVE)

            # Calculate metrics
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                "account_id": account_id,
                "status": "success",
                "messages_processed": len(processed),
                "total_messages": len(messages),
                "duration_seconds": duration,
            }

            logger.info("Account polling completed successfully", extra=result)
            return result

        except ConnectionError as e:
            # Let the calling task handle retries for connection errors
            logger.warning("Connection error", extra={"error": str(e)})
            raise

        except EmailAccount.DoesNotExist:
            logger.warning("Email account not found", extra={"account_id": account_id})
            return {"account_id": account_id, "status": "not_found"}

        except Exception as e:
            logger.exception("Unhandled error polling account", extra={"error": str(e)})
            return {"account_id": account_id, "status": "error", "error": str(e)}

    @transaction.atomic
    def process_message(self, account, message_data):
        """
        Process a single email message.

        Args:
            account: EmailAccount instance
            message_data: Dictionary with message data from adapter

        Returns:
            Processed EmailMessage instance
        """
        # Check if message already exists to avoid duplicates
        message_id = message_data.get("message_id")
        existing = EmailMessage.objects.filter(message_id=message_id).first()

        if existing:
            logger.info("Message already exists", extra={"message_id": message_id})
            return existing

        # Create new message
        email_message = EmailMessage(
            account=account,
            message_id=message_id,
            conversation_id=message_data.get("conversation_id", message_id),
            subject=message_data.get("subject", ""),
            sender=message_data.get("sender", ""),
            recipient=message_data.get("recipient", ""),
            cc=message_data.get("cc", ""),
            body=message_data.get("body", ""),
            received_at=message_data.get("received_at", timezone.now()),
            status=MessageStatus.RECEIVED,
            direction=MessageDirection.INBOUND,
            attachments=message_data.get("attachments", []),
        )
        email_message.save()

        # Apply rules if configured
        if config.AUTO_CATEGORIZATION_ENABLED:
            self._apply_rules(account, email_message)

        return email_message

    def _update_account_status(self, account, status):
        """
        Update account status and last poll time.

        Args:
            account: EmailAccount instance
            status: New status value
        """
        account.status = status
        account.last_poll_at = timezone.now()
        account.save(update_fields=["status", "last_poll_at", "updated_at"])

        logger.info(
            "Account status updated",
            extra={"account_id": account.id, "status": status},
        )

    def _apply_rules(self, account, message):
        """
        Apply account rules to an incoming message.

        Args:
            account: EmailAccount instance
            message: EmailMessage instance
        """
        # Get account rules ordered by priority
        rules = account.rules.filter(is_active=True).order_by("priority")

        if not rules.exists():
            return

        logger.info(
            f"Applying {rules.count()} rules to message",
            extra={"message_id": message.id},
        )

        for rule in rules:
            try:
                # Check if rule conditions match
                if self._rule_matches(rule, message):
                    # Execute rule action
                    self._execute_rule_action(rule, message)

                    # If rule specifies stop processing, exit
                    if rule.stop_processing:
                        break
            except Exception as e:
                logger.error(
                    "Error applying rule",
                    extra={
                        "rule_id": rule.id,
                        "message_id": message.id,
                        "error": str(e),
                    },
                )

    def _rule_matches(self, rule, message):
        """
        Check if a rule's conditions match a message.

        Args:
            rule: Rule instance
            message: EmailMessage instance

        Returns:
            Boolean indicating if rule matches
        """
        conditions = rule.conditions or {}

        # Check sender contains
        if "sender_contains" in conditions:
            if conditions["sender_contains"] not in message.sender:
                return False

        # Check subject contains
        if "subject_contains" in conditions:
            if conditions["subject_contains"] not in message.subject:
                return False

        # Check body contains
        if "body_contains" in conditions:
            if conditions["body_contains"] not in message.body:
                return False

        # Check has attachments
        if conditions.get("has_attachment"):
            if not message.attachments:
                return False

        return True

    def _execute_rule_action(self, rule, message):
        """
        Execute a rule's action on a message.

        Args:
            rule: Rule instance
            message: EmailMessage instance
        """
        from ..enums import RuleAction

        action = rule.action
        logger.info(
            "Executing rule action",
            extra={"rule_id": rule.id, "action": action, "message_id": message.id},
        )

        # Update message based on rule action
        if action == RuleAction.TAG:
            tags = message.tags or []
            tags.append(rule.action_data.get("tag"))
            message.tags = tags
            message.save(update_fields=["tags"])

        elif action == RuleAction.ASSIGN:
            message.assigned_to = rule.action_data.get("user_id")
            message.save(update_fields=["assigned_to"])

        elif action == RuleAction.PRIORITY:
            message.priority = rule.action_data.get("priority")
            message.save(update_fields=["priority"])

        # Other actions can be implemented here


# Convenience functions that use the service
def poll_and_process_account(account_id, request=None):
    """
    Poll an email account and process incoming messages.

    Args:
        account_id: ID of the account to poll
        request: Optional request object

    Returns:
        Dictionary with poll results
    """
    service = PollingService(request)
    return service.poll_and_process_account(account_id)


def process_message(account, message_data, request=None):
    """
    Process a single email message.

    Args:
        account: EmailAccount instance
        message_data: Dictionary with message data
        request: Optional request object

    Returns:
        Processed EmailMessage instance
    """
    service = PollingService(request)
    return service.process_message(account, message_data)
