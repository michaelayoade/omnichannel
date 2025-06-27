"""Email integration services package.

This package contains service modules for email integration functionality,
separated by domain responsibility.
"""

from .account_service import (
    create_account,
    delete_account,
    get_account_by_id,
    list_accounts,
    update_account,
    validate_account_settings,
)
from .message_service import (
    forward_message,
    get_message_by_id,
    list_messages,
    reply_to_message,
    send_message,
)
from .polling_service import poll_and_process_account, process_message

# Re-export all services for backward compatibility
__all__ = [
    "create_account",
    "update_account",
    "delete_account",
    "get_account_by_id",
    "list_accounts",
    "validate_account_settings",
    "poll_and_process_account",
    "process_message",
    "send_message",
    "reply_to_message",
    "forward_message",
    "get_message_by_id",
    "list_messages",
]
