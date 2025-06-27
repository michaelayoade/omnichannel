"""Tests for custom encrypted model fields.

This module tests the behavior of the EncryptedCharField and EncryptedTextField
to ensure they correctly handle encryption and decryption of data.
"""

from unittest import mock

from django.db import models
from django.test import TestCase

from ..models.fields import EncryptedCharField, EncryptedTextField


class TestModel(models.Model):
    """Test model for field testing."""

    encrypted_char = EncryptedCharField(max_length=100)
    encrypted_text = EncryptedTextField()

    class Meta:
        app_label = "email_integration"
        # Use a temporary test database table
        managed = False


class EncryptedFieldsTestCase(TestCase):
    """Test case for encrypted model fields."""

    def setUp(self):
        """Set up test environment."""
        # Mock encryption settings and functions
        self.patcher1 = mock.patch("email_integration.models.fields.encrypt_value")
        self.mock_encrypt = self.patcher1.start()
        self.mock_encrypt.side_effect = lambda x: f"encrypted:{x}"

        self.patcher2 = mock.patch("email_integration.models.fields.decrypt_value")
        self.mock_decrypt = self.patcher2.start()
        self.mock_decrypt.side_effect = lambda x: x.replace("encrypted:", "")

        self.patcher3 = mock.patch("email_integration.models.fields.get_config")
        self.mock_get_config = self.patcher3.start()
        self.mock_get_config.return_value = True  # Enable encryption

    def tearDown(self):
        """Clean up after tests."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    def test_encrypted_char_field(self):
        """Test EncryptedCharField behavior."""
        field = EncryptedCharField(max_length=100)

        # Test encryption
        encrypted_value = field.get_prep_value("test_value")
        assert encrypted_value == "encrypted:test_value"
        self.mock_encrypt.assert_called_with("test_value")

        # Test decryption from db
        decrypted_value = field.from_db_value("encrypted:test_value", None, None)
        assert decrypted_value == "test_value"
        self.mock_decrypt.assert_called_with("encrypted:test_value")

        # Test to_python
        python_value = field.to_python("encrypted:test_value")
        assert python_value == "test_value"

    def test_encrypted_text_field(self):
        """Test EncryptedTextField behavior."""
        field = EncryptedTextField()

        # Test encryption
        encrypted_value = field.get_prep_value("test_value")
        assert encrypted_value == "encrypted:test_value"

        # Test decryption
        decrypted_value = field.from_db_value("encrypted:test_value", None, None)
        assert decrypted_value == "test_value"

        # Test to_python
        python_value = field.to_python("encrypted:test_value")
        assert python_value == "test_value"

    def test_disabled_encryption(self):
        """Test fields with encryption disabled."""
        self.mock_get_config.return_value = False

        field = EncryptedCharField(max_length=100)
        value = "test_value"

        # Should not encrypt or decrypt when disabled
        assert field.get_prep_value(value) == value
        assert field.from_db_value(value, None, None) == value

        # Encryption functions should not be called
        self.mock_encrypt.assert_not_called()
        self.mock_decrypt.assert_not_called()

    def test_none_handling(self):
        """Test handling of None values."""
        field = EncryptedCharField(max_length=100)

        # None should pass through untouched
        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) is None
        assert field.to_python(None) is None

    def test_error_handling(self):
        """Test error handling during decryption."""
        field = EncryptedCharField(max_length=100)

        # Simulate decryption error
        self.mock_decrypt.side_effect = ValueError("Invalid token")

        # Should return the original value on error
        original = "invalid:value"
        result = field.from_db_value(original, None, None)
        assert result == original

        # Reset side effect
        self.mock_decrypt.side_effect = lambda x: x.replace("encrypted:", "")

    def test_field_check(self):
        """Test field validation checks."""
        field = EncryptedCharField(max_length=100)

        # Should pass with encryption key available
        assert len(field.check()) == 0

        # Should fail when encryption is enabled but key is missing
        self.mock_get_config.return_value = None
        errors = field.check()
        assert len(errors) == 1
        assert errors[0].id == "email_integration.E001"
