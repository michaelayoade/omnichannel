"""email_integration.channels.registry

Central registry for mapping channel keys to concrete adapter implementations.
This allows for a decoupled, dependency-injection-style architecture where
higher-level services (like Celery tasks) can dynamically load the correct
adapter based on an account's configuration.

To register a new channel:
1.  Create a service class that implements BaseInboundAdapter or BaseOutboundAdapter.
2.  Add a corresponding key to the Channel enum in `enums.py`.
3.  Map the key to the class in the CHANNEL_REGISTRY dictionary below.
"""

from __future__ import annotations

import logging
from typing import Type, Union

from ..models import EmailAccount
from .adapters.base import BaseInboundAdapter, BaseOutboundAdapter
from .services.imap_service import IMAPService
from .services.smtp_service import SMTPService

logger = logging.getLogger(__name__)

# Type alias for adapter classes
AdapterClass = Union[Type[BaseInboundAdapter], Type[BaseOutboundAdapter]]

# Central registry mapping channel keys to adapter classes
CHANNEL_REGISTRY: dict[str, AdapterClass] = {
    "imap": IMAPService,
    "smtp": SMTPService,
}


def get_adapter(
    channel_key: str, account: EmailAccount
) -> Union[BaseInboundAdapter, BaseOutboundAdapter]:
    """Factory function to get an instantiated channel adapter.

    Args:
        channel_key: The channel identifier (e.g., 'imap', 'smtp').
        account: The EmailAccount instance to pass to the adapter.

    Returns:
        An instantiated adapter instance.

    Raises:
        ValueError: If the channel_key is not found in the registry.
    """
    adapter_class = CHANNEL_REGISTRY.get(channel_key)

    if not adapter_class:
        logger.error("Unknown channel key '%s' requested from registry.", channel_key)
        raise ValueError(f"Adapter for channel '{channel_key}' not found.")

    return adapter_class(account)
