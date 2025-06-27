from celery import shared_task
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger, with_request_id

from .. import config, services
from ..exceptions import ConnectionError
from ..models import EmailAccount

logger = ContextLogger(__name__)


@shared_task(
    bind=True, max_retries=config.MAX_RETRIES, default_retry_delay=config.RETRY_DELAY,
)
@with_request_id
def poll_email_account(self, account_id: int, _request_id=None):
    """Celery task to poll a specific email account for new messages.
    This task is a thin wrapper around the `poll_and_process_account` service.
    It handles transient connection errors with retries.
    """
    # Set task context for all log messages from this task
    task_id = self.request.id
    logger.set_context(
        request_id=_request_id,
        task_id=task_id,
        account_id=account_id,
        task_name="poll_email_account",
        retry_count=self.request.retries,
    )

    try:
        logger.info("Starting email account polling task")
        result = services.poll_and_process_account(account_id)
        logger.info("Email account polling completed successfully")
        return result
    except EmailAccount.DoesNotExist:
        # This is not an error, the account was likely deleted or disabled.
        # The service has already logged this.
        return None
    except ConnectionError as e:
        logger.warning(
            "Connection error polling account. Scheduling retry.",
            extra={
                "error": str(e),
                "retry_count": self.request.retries,
                "next_retry": timezone.now()
                + timezone.timedelta(seconds=config.RETRY_DELAY),
            },
        )
        raise self.retry(exc=e)
    except Exception as e:
        # The service layer handles all other exceptions and logs them.
        # This catch is a final safeguard.
        logger.exception("Unexpected error in polling task", extra={"error": str(e)})
        return {"account_id": account_id, "status": "unhandled_task_error"}


@shared_task
@with_request_id
def poll_all_email_accounts(_request_id=None):
    """Poll all active email accounts for new messages."""
    task_start_time = timezone.now()

    # Set context for this batch job
    logger.set_context(
        request_id=_request_id,
        task_name="poll_all_email_accounts",
        batch_start_time=task_start_time.isoformat(),
    )

    # Use model's enum values instead of hardcoding status
    from ..enums import AccountStatus

    # Use select_related to optimize database queries
    accounts = EmailAccount.objects.filter(
        status=AccountStatus.ACTIVE, auto_polling_enabled=True,
    ).select_related(
        "organization",
    )  # Add any other related fields needed

    account_count = accounts.count()
    logger.info(
        f"Found {account_count} active accounts for polling",
        extra={"account_count": account_count},
    )

    results = []
    skipped = 0
    errors = 0

    for account in accounts:
        try:
            # Use context manager pattern for account-specific logging
            with logger.context(account_id=account.id, email=account.email_address):
                # Check if enough time has passed since last poll
                if account.last_poll_at:
                    time_since_poll = timezone.now() - account.last_poll_at
                    poll_frequency_seconds = account.poll_frequency

                    if time_since_poll.total_seconds() < poll_frequency_seconds:
                        logger.debug(
                            "Skipping account - polled recently",
                            extra={
                                "last_poll": account.last_poll_at.isoformat(),
                                "next_poll_due": (
                                    account.last_poll_at
                                    + timezone.timedelta(seconds=poll_frequency_seconds)
                                ).isoformat(),
                            },
                        )
                        skipped += 1
                        continue

                # Poll the account
                logger.info("Scheduling poll for account")
                result = poll_email_account.delay(account.id)

                results.append(
                    {
                        "account_id": account.id,
                        "email_address": account.email_address,
                        "task_id": result.id,
                        "scheduled_at": timezone.now().isoformat(),
                    },
                )
        except Exception as e:
            errors += 1
            logger.exception(
                "Failed to schedule polling for account",
                extra={"account_id": account.id, "error": str(e)},
            )

    # Calculate task metrics
    task_duration = (timezone.now() - task_start_time).total_seconds()
    successful = len(results)

    logger.info(
        "Email polling batch completed",
        extra={
            "successful": successful,
            "skipped": skipped,
            "errors": errors,
            "total": account_count,
            "duration_seconds": task_duration,
        },
    )

    return {
        "scheduled": successful,
        "skipped": skipped,
        "errors": errors,
        "total_accounts": account_count,
        "duration_seconds": task_duration,
        "tasks": results,
    }
