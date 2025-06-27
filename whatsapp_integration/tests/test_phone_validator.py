"""
Tests for WhatsApp phone number validator utilities.

This module contains tests for the security and functionality of phone validation,
which is critical for preventing injection attacks and ensuring proper API requests.
"""
import unittest
from unittest import mock

import pytest

from whatsapp_integration.utils.phone_validator import (
    DEFAULT_COUNTRY_CODE,
    MAX_PHONE_DIGITS,
    MIN_PHONE_DIGITS,
    format_phone,
    is_valid_phone,
    normalize_phone,
    strip_non_numeric,
)


class TestPhoneValidator:
    """Test suite for WhatsApp phone number validation utilities."""

    @pytest.mark.parametrize(
        "phone_input,expected",
        [
            # Valid phone numbers in different formats
            ("+1234567890", True),
            ("1234567890", True),
            ("+44 7911 123456", True),
            ("(555) 123-4567", True),
            # Invalid phone numbers
            ("12345", False),  # Too short
            ("+123456789012345678", False),  # Too long
            ("abcdefghij", False),  # Non-numeric
            ("", False),  # Empty
            (None, False),  # None
        ],
    )
    def test_is_valid_phone(self, phone_input, expected):
        """Test phone number validation against various inputs."""
        result = is_valid_phone(phone_input)
        assert result == expected

    @pytest.mark.parametrize(
        "phone_input,expected",
        [
            ("+1234567890", "1234567890"),  # Strip leading '+'
            ("(555) 123-4567", "5551234567"),  # Strip formatting
            ("555.123.4567", "5551234567"),  # Strip periods
            ("555-123-4567", "5551234567"),  # Strip dashes
            ("abcd1234efgh", "1234"),  # Strip non-numeric
            ("", ""),  # Handle empty
            (None, ""),  # Handle None
        ],
    )
    def test_strip_non_numeric(self, phone_input, expected):
        """Test stripping non-numeric characters from phone numbers."""
        result = strip_non_numeric(phone_input)
        assert result == expected

    @pytest.mark.parametrize(
        "phone_input,country_code,expected",
        [
            ("5551234567", None, f"{DEFAULT_COUNTRY_CODE}5551234567"),  # Default country code
            ("5551234567", "44", "445551234567"),  # Specific country code
            ("+15551234567", None, "15551234567"),  # Already has country code
            ("15551234567", None, "15551234567"),  # Already has country code without +
            ("+445551234567", "1", "445551234567"),  # Keep existing country code
            ("", None, ""),  # Handle empty
            (None, None, ""),  # Handle None
        ],
    )
    def test_format_phone(self, phone_input, country_code, expected):
        """Test phone number formatting with various country codes."""
        result = format_phone(phone_input, country_code)
        assert result == expected

    @pytest.mark.parametrize(
        "phone_input,expected",
        [
            # Valid but varied formats
            ("+1 (555) 123-4567", "15551234567"),
            ("555.123.4567", f"{DEFAULT_COUNTRY_CODE}5551234567"),
            ("(555) 123-4567", f"{DEFAULT_COUNTRY_CODE}5551234567"),
            # Edge cases
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalize_phone(self, phone_input, expected):
        """Test complete phone normalization process."""
        result = normalize_phone(phone_input)
        assert result == expected

    def test_constants_validation(self):
        """Verify security constants are properly defined."""
        # This test ensures we don't accidentally change security boundaries
        assert MIN_PHONE_DIGITS >= 10, "Min digits should be at least 10 for security"
        assert MAX_PHONE_DIGITS <= 15, "Max digits should be at most 15 per E.164"
        assert DEFAULT_COUNTRY_CODE.isdigit(), "Country code should be numeric only"


if __name__ == "__main__":
    unittest.main()
