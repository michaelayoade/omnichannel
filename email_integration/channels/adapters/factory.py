"""
Factory module for creating appropriate email adapter instances.

This module implements the factory pattern to create and configure the
appropriate email protocol adapter based on account settings and account type.
"""

from django.utils.module_loading import import_string

from omnichannel_core.utils.logging import ContextLogger

from ...enums import Channel, Protocol
from ...exceptions import ConfigurationError

logger = ContextLogger(__name__)


def get_adapter(account, adapter_type=None):
    """
    Factory function to create and return the appropriate adapter for an account.

    Args:
        account: EmailAccount instance
        adapter_type: Optional adapter type (inbound or outbound)

    Returns:
        Configured adapter instance

    Raises:
        ConfigurationError: If adapter cannot be determined or created
    """
    if not account:
        raise ConfigurationError("Account is missing or invalid")

    # Determine adapter class path based on account configuration
    adapter_path = _determine_adapter_path(account, adapter_type)

    try:
        # Dynamically import the adapter class
        adapter_class = import_string(adapter_path)

        # Create and configure the adapter
        adapter = adapter_class(account)

        logger.debug(
            "Created email adapter",
            extra={
                "account_id": account.id,
                "adapter_path": adapter_path,
                "adapter_type": adapter_type or "default",
            },
        )
        return adapter

    except (ImportError, AttributeError) as e:
        logger.error(
            "Failed to create adapter",
            extra={
                "account_id": account.id,
                "adapter_path": adapter_path,
                "error": str(e),
            },
        )
        raise ConfigurationError(f"Failed to create adapter: {str(e)}")


def _determine_adapter_path(account, adapter_type=None):
    """
    Determine which adapter class to use based on account settings.

    Args:
        account: EmailAccount instance
        adapter_type: Optional explicit adapter type (inbound or outbound)

    Returns:
        String with import path to adapter class

    Raises:
        ConfigurationError: If adapter type cannot be determined
    """
    base_path = "email_integration.channels.adapters"

    # If explicit adapter type is provided, use it
    if adapter_type == "inbound":
        protocol = account.incoming_protocol
        if protocol == Protocol.IMAP:
            return f"{base_path}.imap.IMAPAdapter"
        elif protocol == Protocol.POP3:
            return f"{base_path}.pop3.POP3Adapter"
    elif adapter_type == "outbound":
        channel = account.outbound_channel
        if channel == Channel.SMTP:
            return f"{base_path}.smtp.SMTPAdapter"

    # Otherwise determine based on account configuration
    if adapter_type is None:
        # Default to determining based on default channel
        if account.inbound_channel == Channel.IMAP:
            return f"{base_path}.imap.IMAPAdapter"
        elif account.inbound_channel == Channel.POP3:
            return f"{base_path}.pop3.POP3Adapter"
        elif account.inbound_channel == Channel.GMAIL_API:
            return f"{base_path}.gmail.GmailAdapter"
        elif account.inbound_channel == Channel.OUTLOOK_API:
            return f"{base_path}.outlook.OutlookAdapter"

    # If we get here, we couldn't determine the adapter type
    raise ConfigurationError(f"Could not determine adapter for account {account.id}")
