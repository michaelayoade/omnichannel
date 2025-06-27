"""email_integration.tasks

This package contains all Celery tasks for the email integration app,
organized by domain.
"""

from .maintenance import (
    cleanup_old_emails,
    process_bounced_emails,
    sync_email_templates,
    update_email_statistics,
)
from .polling import poll_all_email_accounts, poll_email_account
from .rules import process_email_rules
from .sending import send_email_task

__all__ = [
    "send_email_task",
    "poll_email_account",
    "poll_all_email_accounts",
    "process_email_rules",
    "cleanup_old_emails",
    "update_email_statistics",
    "process_bounced_emails",
    "sync_email_templates",
]
