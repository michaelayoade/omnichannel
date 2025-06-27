import logging

from celery import shared_task

from ..channels.adapters.base import BaseOutboundAdapter
from ..channels.registry import get_adapter
from ..models import EmailMessage
from ..rules_engine import execute_rule, rule_matches

logger = logging.getLogger(__name__)


@shared_task
def process_email_rules(email_message_id: int):
    """Process email rules for a received message."""
    try:
        from ..models import EmailRule

        message = EmailMessage.objects.get(id=email_message_id)
        account = message.account

        # Rule actions require an outbound adapter.
        adapter = get_adapter(account.outbound_channel, account)
        if not isinstance(adapter, BaseOutboundAdapter):
            raise TypeError(
                f"Adapter for {account.outbound_channel} is not an outbound adapter.",
            )

        # Get applicable rules for the account
        rules = EmailRule.objects.filter(account=account, is_active=True).order_by(
            "priority",
        )

        for rule in rules:
            try:
                if rule_matches(rule, message):
                    execute_rule(adapter, rule, message)
                    logger.info(f"Applied rule '{rule.name}' to message {message.id}")

            except Exception as e:
                logger.error(f"Error processing rule '{rule.name}': {e}")

    except EmailMessage.DoesNotExist:
        logger.error(f"Email message {email_message_id} not found")
    except Exception as e:
        logger.error(
            f"Error processing email rules for message {email_message_id}: {e}",
        )
