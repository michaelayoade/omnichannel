"""Custom model fields for the email integration app.

This module provides custom Django model fields with encryption
and other specialized behaviors.
"""

from django.core import checks
from django.db import models

from ..config import get_config
from ..utils.crypto import decrypt_value, encrypt_value


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts and decrypts its value
    using the application's encryption utilities.

    The field behaves exactly like a normal CharField except that its value
    is encrypted in the database using our custom encryption service.
    """

    description = "CharField that transparently encrypts and decrypts its values"

    def __init__(self, *args, **kwargs):
        # Ensure max_length is sufficient for encrypted values
        if "max_length" in kwargs:
            kwargs["max_length"] = max(kwargs["max_length"] * 2, 500)
        else:
            kwargs["max_length"] = 500

        self.encryption_enabled = get_config("ENCRYPTION_ENABLED", True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs

    def get_internal_type(self):
        return "CharField"

    def get_prep_value(self, value):
        # Encrypt the value before saving to database
        if value is None or not self.encryption_enabled:
            return value

        # Encrypt and return the value
        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        # Decrypt the value when loaded from database
        if value is None or not self.encryption_enabled:
            return value

        try:
            return decrypt_value(value)
        except Exception:
            # If decryption fails, return the encrypted value
            # This makes debugging easier and avoids app crashes
            return value

    def to_python(self, value):
        if value is None:
            return value

        # If the value is already a string, it might already be decrypted
        if isinstance(value, str):
            try:
                # Try to decrypt in case it's an encrypted value
                if self.encryption_enabled and value.startswith("gAAAAA"):
                    return decrypt_value(value)
                return value
            except Exception:
                # If decryption fails, it might be a plain value
                return value

        return str(value)

    def check(self, **kwargs):
        # Run normal field checks first
        errors = super().check(**kwargs)

        # Custom field checks
        if get_config("ENCRYPTION_KEY", None) is None and self.encryption_enabled:
            errors.append(
                checks.Error(
                    "EncryptedCharField requires ENCRYPTION_KEY to be set",
                    obj=self,
                    id="email_integration.E001",
                ),
            )

        return errors


class EncryptedTextField(models.TextField):
    """TextField that transparently encrypts and decrypts its value.

    Similar to EncryptedCharField but for larger text values.
    """

    description = "TextField that transparently encrypts and decrypts its values"

    def __init__(self, *args, **kwargs):
        self.encryption_enabled = get_config("ENCRYPTION_ENABLED", True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs

    def get_internal_type(self):
        return "TextField"

    def get_prep_value(self, value):
        if value is None or not self.encryption_enabled:
            return value

        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        if value is None or not self.encryption_enabled:
            return value

        try:
            return decrypt_value(value)
        except Exception:
            return value

    def to_python(self, value):
        if value is None:
            return value

        if isinstance(value, str):
            try:
                if self.encryption_enabled and value.startswith("gAAAAA"):
                    return decrypt_value(value)
                return value
            except Exception:
                return value

        return str(value)

    def check(self, **kwargs):
        errors = super().check(**kwargs)

        if get_config("ENCRYPTION_KEY", None) is None and self.encryption_enabled:
            errors.append(
                checks.Error(
                    "EncryptedTextField requires ENCRYPTION_KEY to be set",
                    obj=self,
                    id="email_integration.E001",
                ),
            )

        return errors
