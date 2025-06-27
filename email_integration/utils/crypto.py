"""
Cryptography utilities for email integration.

This module provides tools for encrypting and decrypting sensitive data
such as email credentials with proper key management.
"""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from omnichannel_core.utils.logging import ContextLogger

from ..config import ENCRYPTION_KEY, ENCRYPTION_SALT

logger = ContextLogger(__name__)


class FieldEncryption:
    """
    Utility class for field-level encryption of sensitive data.

    This implementation uses Fernet symmetric encryption with key
    derivation from an environment variable.
    """

    @classmethod
    def _get_key(cls):
        """
        Get or generate the encryption key.

        This method derives a secure key using PBKDF2HMAC from the
        ENCRYPTION_KEY and ENCRYPTION_SALT environment variables.

        Returns:
            Fernet key for encryption/decryption
        """
        if not ENCRYPTION_KEY:
            logger.warning("No encryption key configured, using insecure default")
            # Dev-only fallback, should never be used in production
            key = b"insecure_dev_only_key_do_not_use_in_production!"
        else:
            key = ENCRYPTION_KEY.encode("utf-8")

        # Use configured salt or generate one
        if ENCRYPTION_SALT:
            salt = base64.b64decode(ENCRYPTION_SALT)
        else:
            # In production, salt should be persistent and stored securely
            salt = os.urandom(16)

        # Derive a secure key with PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        derived_key = base64.urlsafe_b64encode(kdf.derive(key))
        return derived_key

    @classmethod
    def encrypt(cls, value):
        """
        Encrypt a sensitive value.

        Args:
            value: String value to encrypt

        Returns:
            Base64-encoded encrypted data
        """
        if not value:
            return None

        try:
            # Convert to bytes if needed
            if isinstance(value, str):
                value = value.encode("utf-8")

            # Create the Fernet instance
            f = Fernet(cls._get_key())

            # Encrypt the value
            encrypted = f.encrypt(value)

            # Return base64 string
            return base64.urlsafe_b64encode(encrypted).decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            # Return None on failure instead of exposing plain value
            return None

    @classmethod
    def decrypt(cls, encrypted_value):
        """
        Decrypt an encrypted value.

        Args:
            encrypted_value: Encrypted string to decrypt

        Returns:
            Original string or None if decryption fails
        """
        if not encrypted_value:
            return None

        try:
            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value)

            # Create the Fernet instance
            f = Fernet(cls._get_key())

            # Decrypt the value
            decrypted = f.decrypt(encrypted_bytes)

            # Return as string
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            return None


def encrypt_value(value):
    """
    Convenience function to encrypt a value.

    Args:
        value: String value to encrypt

    Returns:
        Encrypted string
    """
    return FieldEncryption.encrypt(value)


def decrypt_value(encrypted_value):
    """
    Convenience function to decrypt a value.

    Args:
        encrypted_value: Encrypted string

    Returns:
        Original string or None
    """
    return FieldEncryption.decrypt(encrypted_value)
