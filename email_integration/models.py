"""This module re-exports all email-related models from the
``email_integration.models`` package for backward compatibility.

New code should import directly from the relevant submodule, e.g.,
`from email_integration.models.accounts import EmailAccount`.
"""

# Re-export all models from the new `models` package.
from .models import *  # noqa: F403

# Also re-export __all__ to be explicit about the public API.
