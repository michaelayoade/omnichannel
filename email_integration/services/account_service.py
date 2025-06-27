"""Account management service for email integration.

This module handles all operations related to email accounts including:
- Creation, updating, and deletion of accounts
- Validation of account settings
- Listing and filtering accounts
"""

from django.db import transaction
from django.utils import timezone

from omnichannel_core.utils.logging import ContextLogger, with_request_id

from .. import config
from ..enums import AccountStatus
from ..exceptions import ValidationError
from ..models import EmailAccount
from .base_service import BaseService

logger = ContextLogger(__name__)


class AccountService(BaseService):
    """Service for managing email accounts."""

    @transaction.atomic
    def create_account(self, data, organization_id=None, user=None):
        """Create a new email account.

        Args:
        ----
            data: Dictionary containing account data
            organization_id: Optional organization ID
            user: Optional user creating the account

        Returns:
        -------
            Newly created EmailAccount instance

        Raises:
        ------
            ValidationError: If account data is invalid

        """
        # Set context for logging
        self.logger.set_context(
            action="create_account",
            email=data.get("email_address"),
            organization_id=organization_id,
            user_id=user.id if user else None,
        )

        try:
            # Validate settings before saving
            self._validate_account_settings(data)

            # Create the account
            account = EmailAccount(
                email_address=data["email_address"],
                username=data.get("username") or data["email_address"].split("@")[0],
                display_name=data.get("display_name", ""),
                organization_id=organization_id,
                status=AccountStatus.ACTIVE,
                auto_polling_enabled=data.get("auto_polling_enabled", True),
                poll_frequency=data.get("poll_frequency", config.POLLING_INTERVAL),
                server_settings=data.get("server_settings", {}),
                created_by=user.id if user else None,
                created_at=timezone.now(),
            )
            account.save()

            self.log_transaction(
                "create_account", "success", {"account_id": account.id},
            )
            return account

        except Exception as e:
            self.log_transaction("create_account", "error", {"error": str(e)})
            raise

    @transaction.atomic
    def update_account(self, account_id, data, user=None):
        """Update an existing email account.

        Args:
        ----
            account_id: ID of the account to update
            data: Dictionary containing updated account data
            user: Optional user updating the account

        Returns:
        -------
            Updated EmailAccount instance

        Raises:
        ------
            AccountNotFoundError: If account doesn't exist
            ValidationError: If account data is invalid

        """
        # Set context for logging
        self.logger.set_context(
            action="update_account",
            account_id=account_id,
            user_id=user.id if user else None,
        )

        account = self.get_account(account_id)

        try:
            # Only validate server settings if they're being updated
            if "server_settings" in data:
                self._validate_account_settings(data)
                account.server_settings = data["server_settings"]

            # Update other fields
            for field in [
                "email_address",
                "username",
                "display_name",
                "auto_polling_enabled",
                "poll_frequency",
                "status",
            ]:
                if field in data:
                    setattr(account, field, data[field])

            account.updated_at = timezone.now()
            account.updated_by = user.id if user else None
            account.save()

            self.log_transaction(
                "update_account", "success", {"account_id": account.id},
            )
            return account

        except Exception as e:
            self.log_transaction("update_account", "error", {"error": str(e)})
            raise

    @transaction.atomic
    def delete_account(self, account_id, user=None):
        """Delete an email account.

        Args:
        ----
            account_id: ID of the account to delete
            user: Optional user deleting the account

        Returns:
        -------
            Boolean indicating success

        Raises:
        ------
            AccountNotFoundError: If account doesn't exist

        """
        # Set context for logging
        self.logger.set_context(
            action="delete_account",
            account_id=account_id,
            user_id=user.id if user else None,
        )

        account = self.get_account(account_id)

        try:
            # Soft delete by changing status
            account.status = AccountStatus.INACTIVE
            account.updated_at = timezone.now()
            account.updated_by = user.id if user else None
            account.save()

            self.log_transaction(
                "delete_account", "success", {"account_id": account.id},
            )
            return True

        except Exception as e:
            self.log_transaction("delete_account", "error", {"error": str(e)})
            raise

    def get_account_by_id(self, account_id):
        """Get an email account by ID.

        Args:
        ----
            account_id: ID of the account to retrieve

        Returns:
        -------
            EmailAccount instance

        Raises:
        ------
            AccountNotFoundError: If account doesn't exist

        """
        return self.get_account(account_id)

    def list_accounts(self, organization_id=None, status=None, limit=100, offset=0):
        """List email accounts with optional filtering.

        Args:
        ----
            organization_id: Optional organization ID to filter by
            status: Optional account status to filter by
            limit: Maximum number of accounts to return
            offset: Offset for pagination

        Returns:
        -------
            QuerySet of EmailAccount instances

        """
        # Start with all accounts
        queryset = EmailAccount.objects.all()

        # Apply filters
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        if status:
            queryset = queryset.filter(status=status)

        # Order by created date and apply pagination
        return queryset.order_by("-created_at")[offset : offset + limit]

    def _validate_account_settings(self, data):
        """Validate email account settings.

        Args:
        ----
            data: Dictionary containing account data

        Raises:
        ------
            ValidationError: If validation fails

        """
        # Required fields
        if "email_address" not in data:
            raise ValidationError("Email address is required")

        # Email format validation
        if "@" not in data["email_address"]:
            raise ValidationError("Invalid email address format")

        # Server settings validation if provided
        if "server_settings" in data:
            settings = data["server_settings"]

            # IMAP settings
            if not settings.get("imap_server"):
                raise ValidationError("IMAP server is required")
            if "imap_port" not in settings:
                raise ValidationError("IMAP port is required")

            # SMTP settings
            if not settings.get("smtp_server"):
                raise ValidationError("SMTP server is required")
            if "smtp_port" not in settings:
                raise ValidationError("SMTP port is required")

        return True


# Convenience functions that use the service
def create_account(data, organization_id=None, user=None, request=None):
    """Create a new email account."""
    service = AccountService(request)
    return service.create_account(data, organization_id, user)


def update_account(account_id, data, user=None, request=None):
    """Update an existing email account."""
    service = AccountService(request)
    return service.update_account(account_id, data, user)


def delete_account(account_id, user=None, request=None):
    """Delete an email account."""
    service = AccountService(request)
    return service.delete_account(account_id, user)


def get_account_by_id(account_id, request=None):
    """Get an email account by ID."""
    service = AccountService(request)
    return service.get_account_by_id(account_id)


def list_accounts(organization_id=None, status=None, limit=100, offset=0, request=None):
    """List email accounts with optional filtering."""
    service = AccountService(request)
    return service.list_accounts(organization_id, status, limit, offset)


@with_request_id
def validate_account_settings(data, _request_id=None):
    """Validate email account settings."""
    logger.set_context(request_id=_request_id)
    service = AccountService()
    return service._validate_account_settings(data)
