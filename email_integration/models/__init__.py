"""Domain-focused models for the ``email_integration`` app.

Each concept (accounts, messages, threads, etc.) lives in its own module to keep
concerns isolated and the codebase maintainable.  For backward compatibility,
we import the concrete Django model classes here so that
``import email_integration.models as m`` continues to work everywhere.
"""

from __future__ import annotations

# Re-export model classes from their respective modules
from .accounts import EmailAccount, EmailContact
from .bounces import EmailBounce
from .logs import EmailPollLog
from .messages import EmailAttachment, EmailMessage
from .rules import EmailRule
from .templates import EmailTemplate
from .threads import EmailThread

__all__ = [
    "EmailAccount",
    "EmailContact",
    "EmailMessage",
    "EmailAttachment",
    "EmailThread",
    "EmailTemplate",
    "EmailRule",
    "EmailBounce",
    "EmailPollLog",
]
