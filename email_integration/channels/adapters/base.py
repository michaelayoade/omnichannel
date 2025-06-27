"""email_integration.channels.adapters.base

Generic, reusable adapter interface for all communication channels (email,
WhatsApp, SMS, push, etc.).  Concrete channel adapters should inherit from
the relevant base classes and implement the methods relevant to their
capabilities.

Why an adapter?
---------------
We interact with multiple transport mechanisms, each with slightly different
APIs and semantics.  A common abstraction layer allows higher-level code—Celery
tasks, rule engines, UI views—to treat every transport in a uniform way while
still allowing protocol-specific nuances underneath.

Design goals:
• Minimal mandatory surface area.
• Clear separation of inbound vs. outbound capabilities.
• Compatible with dependency-injection / mocking for testing.

Feel free to extend these base classes with extra hooks (e.g. *close*, metrics
helpers, etc.) if future channels require them.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

from email_integration.models import EmailAccount, EmailMessage, EmailPollLog

logger = logging.getLogger(__name__)


class BaseAdapter(abc.ABC):
    """Base class for all adapters, handling common initialization."""

    def __init__(self, account: EmailAccount):
        if not account:
            raise ValueError("EmailAccount must be provided")
        self.account = account

    @abc.abstractmethod
    def validate_credentials(self) -> bool:
        """Validate the credentials for the account."""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover – cosmetic
        return f"<{self.__class__.__name__} account={self.account_id}>"

    @property
    def account_id(self) -> Any:  # noqa: ANN401 – could be UUID/int etc.
        return getattr(self.account, "id", None)


class BaseOutboundAdapter(BaseAdapter):
    """Abstract base class for sending messages (e.g., SMTP)."""

    @abc.abstractmethod
    def send(
        self,
        to_emails: List[str],
        subject: str,
        plain_body: Optional[str] = None,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> EmailMessage:
        """Send a message through the channel."""
        raise NotImplementedError


class BaseInboundAdapter(BaseAdapter):
    """Abstract base class for receiving messages (e.g., IMAP)."""

    @abc.abstractmethod
    def poll(self) -> EmailPollLog:
        """Poll the channel for new messages."""
        raise NotImplementedError
