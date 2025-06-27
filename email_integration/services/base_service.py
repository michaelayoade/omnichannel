"""Base service module with common functionality for email integration services.

This module provides base functionality and common utilities used across
all email integration service modules.
"""

from django.db import transaction
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger

from ..exceptions import AccountNotFoundError
from ..models import EmailAccount


class BaseService:
    """Base service class with common functionality for email services."""

    def __init__(self, request=None):
        """Initialize service with optional request context.

        Args:
        ----
            request: Optional Django request object for context logging

        """
        self.logger = ContextLogger(__name__)
        self.request = request

        # Set context from request if available
        if request:
            self.logger.set_context(
                request_id=getattr(request, "request_id", None),
                user_id=(
                    getattr(request.user, "id", None)
                    if hasattr(request, "user")
                    else None
                ),
                ip_address=self._get_client_ip(request),
            )

    def _get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Get the first IP in case of multiple proxies
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def get_account(self, account_id):
        """Get an email account by ID with proper error handling.

        Args:
        ----
            account_id: The ID of the account to retrieve

        Returns:
        -------
            EmailAccount instance

        Raises:
        ------
            AccountNotFoundError: If account doesn't exist

        """
        try:
            # Use select_related to optimize queries
            return EmailAccount.objects.select_related("organization").get(
                id=account_id,
            )
        except EmailAccount.DoesNotExist:
            self.logger.warning(
                "Email account not found", extra={"account_id": account_id},
            )
            raise AccountNotFoundError(f"Email account with ID {account_id} not found")

    def log_transaction(self, action, status, details=None):
        """Log a transaction with consistent format.

        Args:
        ----
            action: The action being performed
            status: Status of the transaction ('success', 'error', etc.)
            details: Optional dictionary of additional details

        """
        log_data = {
            "action": action,
            "status": status,
            "timestamp": timezone.now().isoformat(),
        }

        if details:
            log_data.update(details)

        if status == "error":
            self.logger.error(f"Error during {action}", extra=log_data)
        else:
            self.logger.info(f"Completed {action}", extra=log_data)

        return log_data

    @staticmethod
    def transaction_atomic(func):
        """Decorator to wrap a function in a database transaction.

        Args:
        ----
            func: The function to wrap

        Returns:
        -------
            Wrapped function with transaction handling

        """

        def wrapper(*args, **kwargs):
            with transaction.atomic():
                return func(*args, **kwargs)

        return wrapper
