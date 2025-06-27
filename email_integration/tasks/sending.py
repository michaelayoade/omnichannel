from celery import shared_task
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger, with_request_id

from .. import config, services
from ..exceptions import AuthenticationError, ConnectionError, SendError
from ..models import EmailAccount

logger = ContextLogger(__name__)


@shared_task(
    bind=True, max_retries=config.MAX_RETRIES, default_retry_delay=config.RETRY_DELAY,
)
@with_request_id
def send_email_task(self, account_id, message_data, _request_id=None):
    """Celery task to send an email asynchronously.

    This task is a thin wrapper around the message_service.send_message service.
    It handles transient connection errors with retries.

    Args:
    ----
        account_id: ID of the email account to send from
        message_data: Dictionary with message data (recipient, subject, body, etc.)
        _request_id: Optional request ID for logging context

    """
    # Set task context for all log messages from this task
    task_id = self.request.id
    logger.set_context(
        request_id=_request_id,
        task_id=task_id,
        account_id=account_id,
        task_name="send_email_task",
        retry_count=self.request.retries,
    )

    try:
        logger.info("Starting email send task")

        # Call the message service to send the email
        result = services.send_message(account_id, message_data)

        logger.info(
            "Email sent successfully",
            extra={
                "message_id": result.id if result else None,
                "recipient": message_data.get("recipient"),
            },
        )
        return {"success": True, "message_id": result.id if result else None}

    except EmailAccount.DoesNotExist:
        # Account not found - log and abort
        logger.warning(
            "Email account not found or inactive", extra={"account_id": account_id},
        )
        return {"success": False, "error": "account_not_found"}

    except AuthenticationError as e:
        # Authentication error - log and abort
        logger.error("Authentication failed for email account", extra={"error": str(e)})
        return {"success": False, "error": "authentication_failed"}

    except ConnectionError as e:
        # Connection error - retry the task
        logger.warning(
            "Connection error sending email. Scheduling retry.",
            extra={
                "error": str(e),
                "retry_count": self.request.retries,
                "next_retry": timezone.now()
                + timezone.timedelta(seconds=config.RETRY_DELAY),
            },
        )
        raise self.retry(exc=e)

    except SendError as e:
        # Sending error - log and abort
        logger.error("Error sending email", extra={"error": str(e)})
        return {"success": False, "error": "send_error"}

    except Exception as e:
        # Catch-all for unexpected issues
        logger.exception("Unexpected error in send task", extra={"error": str(e)})
        return {"success": False, "error": "unexpected_error"}
