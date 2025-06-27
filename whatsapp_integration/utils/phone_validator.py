import logging
import re
from typing import ClassVar

logger = logging.getLogger(__name__)


class PhoneNumberValidator:
    """WhatsApp phone number validation and formatting utility.
    
    Handles international phone number formats according to WhatsApp Business
    API requirements.
    """

    # Constants for phone number validation
    MIN_PHONE_DIGITS: int = 7
    MAX_PHONE_DIGITS: int = 15
    STANDARD_PHONE_LENGTH: int = 10

    # Country code mappings for common countries
    COUNTRY_CODES: ClassVar[dict[str, str]] = {
        "US": "1",
        "CA": "1",
        "UK": "44",
        "DE": "49",
        "FR": "33",
        "IT": "39",
        "ES": "34",
        "BR": "55",
        "IN": "91",
        "AU": "61",
        "JP": "81",
        "CN": "86",
        "RU": "7",
        "MX": "52",
        "AR": "54",
        "ZA": "27",
        "NG": "234",
        "KE": "254",
        "EG": "20",
        "SA": "966",
        "AE": "971",
    }

    @staticmethod
    def clean_phone_number(phone: str) -> str:
        """Remove all non-digit characters from phone number."""
        return re.sub(r"[^\d]", "", phone)

    @staticmethod
    def is_valid_whatsapp_number(phone: str) -> bool:
        """Validate if phone number is in correct WhatsApp format.
        
        WhatsApp numbers should be within valid digit range (excluding country code prefix).
        """
        cleaned = PhoneNumberValidator.clean_phone_number(phone)

        # WhatsApp numbers must be within valid digit range
        if len(cleaned) < PhoneNumberValidator.MIN_PHONE_DIGITS or len(cleaned) > PhoneNumberValidator.MAX_PHONE_DIGITS:
            return False

        # Must contain only digits
        if not cleaned.isdigit():
            return False

        return True

    @staticmethod
    def format_for_whatsapp(
        phone: str, default_country_code: str = "1",
    ) -> str | None:
        """Format phone number for WhatsApp Business API.
        
        Returns phone number in E.164 format without the '+' prefix.

        Args:
        ----
            phone: Raw phone number input
            default_country_code: Default country code to use if not present

        Returns:
        -------
            Formatted phone number or None if invalid

        """
        try:
            cleaned = PhoneNumberValidator.clean_phone_number(phone)

            if not cleaned:
                return None

            # If number already starts with country code, use as-is
            if len(cleaned) >= PhoneNumberValidator.STANDARD_PHONE_LENGTH:
                # Check if it starts with common country codes
                for _country, code in PhoneNumberValidator.COUNTRY_CODES.items():
                    if cleaned.startswith(code) and PhoneNumberValidator.is_valid_whatsapp_number(cleaned):
                        return cleaned

            # If number doesn't have country code, add default
            if len(cleaned) < PhoneNumberValidator.STANDARD_PHONE_LENGTH:
                return None

            # Add default country code
            formatted = f"{default_country_code}{cleaned}"

            if PhoneNumberValidator.is_valid_whatsapp_number(formatted):
                return formatted

            return None

        except Exception as e:
            logger.error(f"Error formatting phone number {phone}: {e}")
            return None

    @staticmethod
    def extract_country_code(phone: str) -> tuple[str | None, str | None]:
        """Extract country code and local number from phone number.
        
        Returns
        -------
            Tuple of (country_code, local_number) or (None, None) if invalid

        """
        cleaned = PhoneNumberValidator.clean_phone_number(phone)

        if not cleaned:
            return None, None

        # Try to match known country codes
        for _country, code in sorted(
            PhoneNumberValidator.COUNTRY_CODES.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            if cleaned.startswith(code):
                local_number = cleaned[len(code) :]
                if len(local_number) >= PhoneNumberValidator.MIN_PHONE_DIGITS:
                    return code, local_number

        return None, None

    @staticmethod
    def normalize_whatsapp_id(wa_id: str) -> str:
        """Normalize WhatsApp ID to ensure consistency.
        
        WhatsApp IDs are phone numbers without '+' or other formatting.
        """
        return PhoneNumberValidator.clean_phone_number(wa_id)

    @staticmethod
    def is_same_number(phone1: str, phone2: str) -> bool:
        """Check if two phone numbers refer to the same number.
        
        Handles different formatting styles.
        """
        normalized1 = PhoneNumberValidator.normalize_whatsapp_id(phone1)
        normalized2 = PhoneNumberValidator.normalize_whatsapp_id(phone2)

        if not normalized1 or not normalized2:
            return False

        # Direct match
        if normalized1 == normalized2:
            return True

        # Try with different country code assumptions
        for _country, code in PhoneNumberValidator.COUNTRY_CODES.items():
            # Check if one has country code and other doesn't
            if normalized1.startswith(code) and not normalized2.startswith(code):
                if normalized1[len(code) :] == normalized2:
                    return True
            elif normalized2.startswith(code) and not normalized1.startswith(code):
                if normalized2[len(code) :] == normalized1:
                    return True

        return False

    @staticmethod
    def get_display_format(phone: str) -> str:
        """Get a human-readable display format for phone number."""
        cleaned = PhoneNumberValidator.clean_phone_number(phone)

        if not cleaned:
            return phone

        # Try to format with country code
        country_code, local_number = PhoneNumberValidator.extract_country_code(cleaned)

        if country_code and local_number:
            # Format as +country (local)
            if len(local_number) == PhoneNumberValidator.STANDARD_PHONE_LENGTH:  # US/CA format
                formatted_local = (
                    f"({local_number[:3]}) {local_number[3:6]}-{local_number[6:]}"
                )
            else:
                # Generic formatting
                formatted_local = local_number

            return f"+{country_code} {formatted_local}"

        # Fallback to original with + prefix
        return f"+{cleaned}"


def validate_and_format_phone(
    phone: str, country_code: str = "1",
) -> tuple[bool, str | None, str]:
    """Validate and format phone number for WhatsApp.
    
    Returns
    -------
        Tuple of (is_valid, formatted_number, error_message)

    """
    if not phone:
        return False, None, "Phone number is required"

    try:
        formatted = PhoneNumberValidator.format_for_whatsapp(phone, country_code)

        if formatted:
            return True, formatted, ""
        return False, None, "Invalid phone number format"

    except Exception as e:
        return False, None, f"Phone validation error: {e!s}"
