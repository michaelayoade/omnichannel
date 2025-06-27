"""Tests for the encryption utilities.

This module tests the field-level encryption and decryption functionality,
ensuring sensitive data is properly protected.
"""

from unittest import mock

import pytest
from django.test import TestCase

from ..utils.crypto import decrypt_value, derive_key, encrypt_value, get_encryption_key


class CryptoUtilsTestCase(TestCase):
    """Test case for cryptography utilities."""

    def setUp(self):
        """Set up test environment."""
        # Mock encryption settings
        self.test_key = b"this-is-a-test-encryption-key-for-unit-tests-only"
        self.test_salt = b"test-salt-value"
        self.patcher1 = mock.patch("email_integration.utils.crypto.get_config")
        self.mock_get_config = self.patcher1.start()
        self.mock_get_config.return_value = self.test_key.decode("utf-8")

    def tearDown(self):
        """Clean up after tests."""
        self.patcher1.stop()

    def test_key_derivation(self):
        """Test that key derivation produces consistent results."""
        key1 = derive_key(self.test_key, self.test_salt)
        key2 = derive_key(self.test_key, self.test_salt)

        # Same inputs should produce same key
        assert key1 == key2

        # Different salt should produce different key
        different_key = derive_key(self.test_key, b"different-salt")
        assert key1 != different_key

        # Key should be 32 bytes (for Fernet)
        assert len(key1) == 32

    def test_encryption_decryption(self):
        """Test that encryption and decryption work correctly."""
        test_values = [
            "simple test string",
            "Complex string with !@#$%^&*()_+=-`~ symbols",
            "String with unicode characters: 你好世界",
            "Very long string " + "x" * 1000,
            "",  # Empty string
        ]

        for value in test_values:
            encrypted = encrypt_value(value)

            # Encrypted value should be different from original
            assert value != encrypted

            # Encrypted value should start with Fernet prefix
            assert encrypted.startswith("gAAAAA")

            # Decryption should recover original value
            decrypted = decrypt_value(encrypted)
            assert value == decrypted

    def test_get_encryption_key(self):
        """Test retrieval of encryption key."""
        # Test with mocked config
        key = get_encryption_key()
        assert key == self.test_key

        # Test fallback for development
        with mock.patch("email_integration.utils.crypto.settings") as mock_settings:
            mock_settings.DEBUG = True
            self.mock_get_config.return_value = None
            key = get_encryption_key()
            assert key is not None

        # Test error in production mode
        with mock.patch("email_integration.utils.crypto.settings") as mock_settings:
            mock_settings.DEBUG = False
            self.mock_get_config.return_value = None
            with pytest.raises(ValueError):
                get_encryption_key()

    @mock.patch("email_integration.utils.crypto.logger")
    def test_decryption_failure(self, mock_logger):
        """Test handling of decryption failures."""
        with pytest.raises(ValueError):
            decrypt_value("not-a-valid-encrypted-value")

        # Logger should record the error
        mock_logger.error.assert_called_once()
