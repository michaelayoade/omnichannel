from omnichannel_core.utils.logging import ContextLogger, with_request_id

from .channels.adapters.base import BaseInboundAdapter
from .channels.registry import get_adapter
from .enums import AccountStatus
from .exceptions import AuthenticationError, ConnectionError, PollingError
from .models import EmailAccount

logger = ContextLogger(__name__)


@with_request_id
def poll_and_process_account(account_id: int, _request_id=None):
    """Polls a specific email account for new messages and processes them.

    This function contains the core business logic for polling an email account,
    handling various outcomes like success, authentication failure, or other errors.

    Args:
    ----
        account_id: The ID of the EmailAccount to poll.

    Returns:
    -------
        A dictionary summarizing the polling result.

    Raises:
    ------
        EmailAccount.DoesNotExist: If the account cannot be found or is not active.
        ConnectionError: If a transient connection issue occurs.
        PollingError: For non-transient polling errors.
        TypeError: If the resolved adapter is not an inbound adapter.

    """
    try:
        # Set context for all subsequent log calls
        logger.set_context(request_id=_request_id, account_id=account_id)

        # Use select_related to fetch related fields in a single query
        account = EmailAccount.objects.select_related(
            "organization",  # Assuming organization is a related field
            "user",  # Assuming account may have a user relation
        ).get(id=account_id, status=AccountStatus.ACTIVE, auto_polling_enabled=True)

        # Add email address to logging context once we have the account
        logger.set_context(email_address=account.email_address)
    except EmailAccount.DoesNotExist:
        logger.warning("Email account not found or inactive for polling.")
        raise  # Re-raise for the caller (task) to handle gracefully.

    try:
        adapter = get_adapter(account.inbound_channel, account)
        if not isinstance(adapter, BaseInboundAdapter):
            raise TypeError(
                f"Adapter for {account.inbound_channel} is not an inbound adapter.",
            )

        poll_log = adapter.poll()

        logger.info(
            f"Email polling completed for {account.email_address}: "
            f"{poll_log.messages_processed} messages processed",
        )

        return {
            "account_id": account_id,
            "messages_processed": poll_log.messages_processed,
            "messages_failed": poll_log.messages_failed,
            "status": poll_log.status,
        }

    except ConnectionError:
        # Re-raise connection errors so the Celery task can retry.
        logger.warning(
            f"Connection error for email account {account_id}. Task will be retried.",
        )
        raise

    except AuthenticationError as e:
        logger.error(
            f"Authentication failed for email account {account_id}. "
            f"Disabling account. Error: {e}",
        )
        account.status = AccountStatus.INACTIVE
        account.last_error_message = (
            f"Authentication failed, account disabled. Details: {e}"
        )
        account.save(update_fields=["status", "last_error_message"])
        return {"account_id": account_id, "status": "authentication_error"}

    except (PollingError, TypeError) as e:
        logger.error(
            f"A non-transient error occurred while polling account {account_id}: {e}",
        )
        account.last_error_message = f"A non-transient polling error occurred: {e}"
        account.save(update_fields=["last_error_message"])
        return {"account_id": account_id, "status": "polling_error"}

    except Exception as e:
        logger.exception(
            f"An unexpected error occurred polling email account {account_id}: {e}",
        )
        account.last_error_message = f"An unexpected error occurred during polling: {e}"
        account.save(update_fields=["last_error_message"])
        return {"account_id": account_id, "status": "unexpected_error"}
