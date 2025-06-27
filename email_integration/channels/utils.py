"""Utility functions for email integration channels.

This module provides reusable utility functions for email operations
including data encoding/decoding, hashing, and string manipulation.
"""

import base64
import hashlib
import re
import uuid


def encode_attachment(content: bytes) -> str:
    """Encode binary attachment content to base64 string.

    Args:
    ----
        content: Binary attachment data

    Returns:
    -------
        Base64-encoded content string

    """
    if not content:
        return ""
    return base64.b64encode(content).decode("utf-8")


def decode_attachment(encoded_content: str) -> bytes:
    """Decode base64 attachment content to binary.

    Args:
    ----
        encoded_content: Base64-encoded content string

    Returns:
    -------
        Binary attachment data

    """
    if not encoded_content:
        return b""
    return base64.b64decode(encoded_content)


def hash_string(value: str) -> str:
    """Create a deterministic hash from a string.

    Args:
    ----
        value: String to hash

    Returns:
    -------
        Hex digest of SHA-256 hash

    """
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_id() -> str:
    """Generate a unique ID string.

    Returns
    -------
        Unique ID string

    """
    return str(uuid.uuid4())


def extract_email_address(full_address: str) -> str:
    """Extract email address from a full address string.

    Args:
    ----
        full_address: Full address string (e.g. "Name <email@example.com>")

    Returns:
    -------
        Email address only

    """
    if not full_address:
        return ""

    # Try to extract email with regex
    match = re.search(r"<([^>]+)>", full_address)
    if match:
        return match.group(1)

    # If no angle brackets, return the whole string with whitespace trimmed
    return full_address.strip()


def parse_address_list(address_string: str) -> list[dict[str, str]]:
    """Parse a comma-separated list of email addresses.

    Args:
    ----
        address_string: String with one or more addresses

    Returns:
    -------
        List of dictionaries with name and email for each address

    """
    if not address_string:
        return []

    result = []
    # Split by commas, but not commas inside quotes
    parts = re.findall(r'(?:[^,"]|"[^"]*")+', address_string)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try to extract name and email
        match = re.match(r'"?([^"<]+)"?\s*<?([^>]*)>?', part)
        if match and match.group(2):
            name = match.group(1).strip()
            email = match.group(2).strip()
            result.append({"name": name, "email": email})
        else:
            # No name found, use the address as both
            email = part.strip()
            result.append({"name": "", "email": email})

    return result


def format_address(name: str, email: str) -> str:
    """Format a name and email into a proper email address string.

    Args:
    ----
        name: Display name
        email: Email address

    Returns:
    -------
        Formatted address string

    """
    if not email:
        return ""

    if name:
        # Quote the name if it contains special characters
        if re.search(r'[,.<>@:;"\[\]\\]', name):
            return f'"{name}" <{email}>'
        return f"{name} <{email}>"
    else:
        return email


def sanitize_subject(subject: str) -> str:
    """Sanitize an email subject line.

    Args:
    ----
        subject: Raw subject line

    Returns:
    -------
        Sanitized subject string

    """
    if not subject:
        return ""

    # Remove control characters
    subject = re.sub(r"[\x00-\x1F\x7F]", "", subject)

    # Limit length
    if len(subject) > 255:
        subject = subject[:252] + "..."

    return subject


def clean_html(html_content: str) -> str:
    """Basic cleanup of HTML content for security.

    Args:
    ----
        html_content: Raw HTML content

    Returns:
    -------
        Cleaned HTML content

    """
    if not html_content:
        return ""

    # Remove potentially dangerous tags and attributes
    # NOTE: This is a basic implementation. In production, use a proper HTML sanitizer.
    cleaned = re.sub(
        r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<iframe[^>]*>.*?</iframe>", "", cleaned, flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<object[^>]*>.*?</object>", "", cleaned, flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<embed[^>]*>.*?</embed>", "", cleaned, flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove on* event handlers
    cleaned = re.sub(
        r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", cleaned, flags=re.IGNORECASE,
    )

    # Remove javascript: URLs
    return re.sub(
        r'(href|src)\s*=\s*["\']javascript:[^"\']*["\']',
        r'\1="#"',
        cleaned,
        flags=re.IGNORECASE,
    )

