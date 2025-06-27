import email.message
import hashlib
import logging
import re
from datetime import datetime
from email.header import decode_header
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailParser:
    """
    Utility class for parsing email messages and extracting information.
    Handles various email formats, encodings, and content types.
    """

    def __init__(self):
        self.customer_patterns = {
            "name": [
                r"(?:my name is|i am|i\'m)\s+([a-zA-Z\s]+)",
                r"(?:name:|full name:)\s*([a-zA-Z\s]+)",
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)",  # Capitalized first last name
            ],
            "phone": [
                r"(?:phone|tel|telephone|mobile|cell)(?:\s*[:#]?\s*)([\d\s\-\(\)\+]{10,})",
                r"(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})",
                r"(\d{3}[-.]?\d{3}[-.]?\d{4})",
            ],
            "email": [
                r"(?:email|e-mail)(?:\s*[:#]?\s*)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            ],
            "company": [
                r"(?:company|organization|business)(?:\s*[:#]?\s*)([a-zA-Z0-9\s&.,]+)",
                r"(?:work for|employed at|works at)\s+([a-zA-Z0-9\s&.,]+)",
            ],
            "address": [
                r"(?:address|location)(?:\s*[:#]?\s*)([a-zA-Z0-9\s,.-]+(?:street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|lane|ln))",
            ],
        }

    def parse_email(self, email_message: email.message.Message) -> Dict:
        """
        Parse an email message and extract all relevant information.

        Args:
            email_message: Email message object

        Returns:
            Dictionary containing parsed email data
        """
        try:
            parsed_data = {
                "message_id": self._get_message_id(email_message),
                "subject": self._decode_header(email_message.get("Subject", "")),
                "from_email": self._parse_email_address(email_message.get("From", ""))[
                    1
                ],
                "from_name": self._parse_email_address(email_message.get("From", ""))[
                    0
                ],
                "to_emails": self._parse_email_list(email_message.get("To", "")),
                "cc_emails": self._parse_email_list(email_message.get("Cc", "")),
                "bcc_emails": self._parse_email_list(email_message.get("Bcc", "")),
                "reply_to": self._parse_email_address(
                    email_message.get("Reply-To", "")
                )[1],
                "date": self._parse_date(email_message.get("Date")),
                "in_reply_to": self._clean_message_id(
                    email_message.get("In-Reply-To", "")
                ),
                "references": email_message.get("References", ""),
                "headers": self._extract_headers(email_message),
                "plain_body": "",
                "html_body": "",
                "attachments": [],
            }

            # Extract body content and attachments
            self._extract_content(email_message, parsed_data)

            # Extract customer information
            parsed_data["customer_info"] = self._extract_customer_info(parsed_data)

            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return {}

    def _get_message_id(self, email_message: email.message.Message) -> str:
        """Extract and clean message ID."""
        message_id = email_message.get("Message-ID", "")
        return self._clean_message_id(message_id)

    def _clean_message_id(self, message_id: str) -> str:
        """Clean message ID by removing angle brackets."""
        return message_id.strip("<>")

    def _decode_header(self, header_value: str) -> str:
        """Decode email header that might be encoded."""
        if not header_value:
            return ""

        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode("utf-8", errors="ignore")
                else:
                    decoded_string += part

            return decoded_string.strip()

        except Exception as e:
            logger.warning(f"Error decoding header '{header_value}': {e}")
            return header_value

    def _parse_email_address(self, address_string: str) -> Tuple[str, str]:
        """
        Parse email address string and return (name, email).

        Args:
            address_string: Email address string like "John Doe <john@example.com>"

        Returns:
            Tuple of (name, email_address)
        """
        if not address_string:
            return "", ""

        try:
            # Decode the address string first
            decoded_address = self._decode_header(address_string)

            # Parse the address
            name, email_addr = parseaddr(decoded_address)

            # Clean up the name
            if name:
                name = name.strip("\"'")

            return name or "", email_addr or ""

        except Exception as e:
            logger.warning(f"Error parsing email address '{address_string}': {e}")
            return "", address_string

    def _parse_email_list(self, address_list: str) -> List[str]:
        """Parse comma-separated list of email addresses."""
        if not address_list:
            return []

        try:
            decoded_list = self._decode_header(address_list)
            emails = []

            # Split by comma and parse each address
            for addr in decoded_list.split(","):
                _, email_addr = self._parse_email_address(addr.strip())
                if email_addr:
                    emails.append(email_addr)

            return emails

        except Exception as e:
            logger.warning(f"Error parsing email list '{address_list}': {e}")
            return []

    def _parse_date(self, date_string: str) -> datetime:
        """Parse email date string to datetime object."""
        if not date_string:
            return timezone.now()

        try:
            # Try to parse using email.utils
            parsed_date = parsedate_to_datetime(date_string)

            # Convert to timezone-aware datetime
            if parsed_date.tzinfo is None:
                parsed_date = timezone.make_aware(parsed_date)

            return parsed_date

        except Exception as e:
            logger.warning(f"Error parsing date '{date_string}': {e}")
            return timezone.now()

    def _extract_headers(self, email_message: email.message.Message) -> Dict:
        """Extract all email headers as dictionary."""
        headers = {}

        for key, value in email_message.items():
            headers[key] = self._decode_header(value)

        return headers

    def _extract_content(self, email_message: email.message.Message, parsed_data: Dict):
        """Extract email body content and attachments."""
        if email_message.is_multipart():
            self._process_multipart(email_message, parsed_data)
        else:
            self._process_single_part(email_message, parsed_data)

    def _process_multipart(
        self, email_message: email.message.Message, parsed_data: Dict
    ):
        """Process multipart email message."""
        for part in email_message.walk():
            if part.is_multipart():
                continue

            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")

            if "attachment" in content_disposition:
                self._process_attachment(part, parsed_data)
            elif content_type == "text/plain":
                self._extract_text_content(part, parsed_data, "plain_body")
            elif content_type == "text/html":
                self._extract_text_content(part, parsed_data, "html_body")
            elif part.get("Content-ID"):
                # Inline attachment
                self._process_inline_attachment(part, parsed_data)

    def _process_single_part(
        self, email_message: email.message.Message, parsed_data: Dict
    ):
        """Process single-part email message."""
        content_type = email_message.get_content_type()

        if content_type == "text/plain":
            self._extract_text_content(email_message, parsed_data, "plain_body")
        elif content_type == "text/html":
            self._extract_text_content(email_message, parsed_data, "html_body")

    def _extract_text_content(
        self, part: email.message.Message, parsed_data: Dict, body_type: str
    ):
        """Extract text content from email part."""
        try:
            # Get the payload
            payload = part.get_payload(decode=True)

            if payload:
                # Try to decode with specified charset
                charset = part.get_content_charset() or "utf-8"
                try:
                    content = payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    # Fallback to utf-8 with error handling
                    content = payload.decode("utf-8", errors="ignore")

                # Clean up the content
                content = self._clean_text_content(content)

                # Append to existing content if any
                if parsed_data.get(body_type):
                    parsed_data[body_type] += "\n\n" + content
                else:
                    parsed_data[body_type] = content

        except Exception as e:
            logger.warning(f"Error extracting text content: {e}")

    def _clean_text_content(self, content: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)
        content = re.sub(r"[ \t]+", " ", content)

        # Remove common email artifacts
        content = re.sub(r"=\d{2}", "", content)  # Quoted-printable artifacts
        content = re.sub(r"=\r?\n", "", content)  # Line breaks in quoted-printable

        return content.strip()

    def _process_attachment(self, part: email.message.Message, parsed_data: Dict):
        """Process email attachment."""
        try:
            filename = part.get_filename()
            if not filename:
                filename = "attachment"

            # Decode filename if needed
            filename = self._decode_header(filename)

            # Get content
            content = part.get_payload(decode=True)
            if not content:
                return

            attachment_data = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "content": content,
                "size": len(content),
                "is_inline": False,
            }

            parsed_data["attachments"].append(attachment_data)

        except Exception as e:
            logger.warning(f"Error processing attachment: {e}")

    def _process_inline_attachment(
        self, part: email.message.Message, parsed_data: Dict
    ):
        """Process inline attachment (e.g., embedded images)."""
        try:
            content_id = part.get("Content-ID", "").strip("<>")
            filename = part.get_filename() or f"inline_{content_id}"

            content = part.get_payload(decode=True)
            if not content:
                return

            attachment_data = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "content": content,
                "content_id": content_id,
                "size": len(content),
                "is_inline": True,
            }

            parsed_data["attachments"].append(attachment_data)

        except Exception as e:
            logger.warning(f"Error processing inline attachment: {e}")

    def _extract_customer_info(self, parsed_data: Dict) -> Dict:
        """Extract customer information from email content."""
        customer_info = {}

        # Combine all text content for analysis
        text_content = (
            f"{parsed_data.get('plain_body', '')} {parsed_data.get('html_body', '')}"
        )

        # Extract information using patterns
        for info_type, patterns in self.customer_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    # Take the first match and clean it
                    value = matches[0].strip()
                    if value and len(value) > 2:  # Avoid very short matches
                        customer_info[info_type] = value
                        break

        # Try to extract name from sender if not found in content
        if "name" not in customer_info and parsed_data.get("from_name"):
            from_name = parsed_data["from_name"]
            # Check if it looks like a real name (not email address)
            if "@" not in from_name and len(from_name.split()) >= 2:
                customer_info["name"] = from_name

        # Clean up extracted phone numbers
        if "phone" in customer_info:
            customer_info["phone"] = self._clean_phone_number(customer_info["phone"])

        return customer_info

    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number."""
        # Remove all non-digit characters except +
        cleaned = re.sub(r"[^\d+]", "", phone)

        # Basic US phone number formatting
        if len(cleaned) == 10:
            return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
        elif len(cleaned) == 11 and cleaned.startswith("1"):
            return f"({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"

        return cleaned

    def generate_message_id(self) -> str:
        """Generate a unique message ID for internal use."""
        return make_msgid(domain="omnichannel.local")


class EmailThreadParser:
    """
    Utility class for detecting and managing email threads.
    Groups related emails into conversation threads.
    """

    def __init__(self):
        self.subject_patterns = [
            r"^(re|fw|fwd):\s*",  # Reply/Forward prefixes
            r"\[.*?\]\s*",  # Subject tags like [URGENT]
            r"^\s*",  # Leading whitespace
        ]

    def generate_thread_id(
        self, subject: str, in_reply_to: str = "", references: str = ""
    ) -> str:
        """
        Generate a thread ID for grouping related emails.

        Args:
            subject: Email subject
            in_reply_to: In-Reply-To header value
            references: References header value

        Returns:
            Thread ID string
        """
        # If we have reply information, extract thread ID from references
        if in_reply_to or references:
            thread_id = self._extract_thread_id_from_references(in_reply_to, references)
            if thread_id:
                return thread_id

        # Otherwise, generate thread ID from normalized subject
        normalized_subject = self._normalize_subject(subject)

        # Create a hash of the normalized subject
        thread_id = hashlib.sha256(normalized_subject.encode("utf-8")).hexdigest()[:16]

        return f"thread_{thread_id}"

    def _extract_thread_id_from_references(
        self, in_reply_to: str, references: str
    ) -> Optional[str]:
        """Extract thread ID from existing message references."""
        # Look for existing thread IDs in references
        all_refs = f"{references} {in_reply_to}".strip()

        # Pattern to match our generated thread IDs
        thread_pattern = r"thread_[a-f0-9]{16}"
        matches = re.findall(thread_pattern, all_refs)

        if matches:
            return matches[0]

        # If no existing thread ID found, try to extract from message IDs
        message_ids = re.findall(r"<([^>]+)>", all_refs)
        if message_ids:
            # Use the first message ID to generate a consistent thread ID
            first_msg_id = message_ids[0]
            thread_id = hashlib.sha256(first_msg_id.encode("utf-8")).hexdigest()[:16]
            return f"thread_{thread_id}"

        return None

    def _normalize_subject(self, subject: str) -> str:
        """Normalize email subject for thread detection."""
        if not subject:
            return "no_subject"

        normalized = subject.lower()

        # Remove common prefixes and patterns
        for pattern in self.subject_patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        # Remove trailing punctuation
        normalized = normalized.rstrip(".,!?;:")

        return normalized or "no_subject"

    def are_messages_in_same_thread(self, msg1_data: Dict, msg2_data: Dict) -> bool:
        """
        Determine if two messages belong to the same thread.

        Args:
            msg1_data: First message parsed data
            msg2_data: Second message parsed data

        Returns:
            True if messages are in same thread
        """
        # Check if either message references the other
        if self._messages_reference_each_other(msg1_data, msg2_data):
            return True

        # Check if subjects are similar enough
        if self._subjects_are_similar(
            msg1_data.get("subject", ""), msg2_data.get("subject", "")
        ):
            return True

        return False

    def _messages_reference_each_other(self, msg1_data: Dict, msg2_data: Dict) -> bool:
        """Check if messages reference each other through headers."""
        msg1_id = msg1_data.get("message_id", "")
        msg2_id = msg2_data.get("message_id", "")

        msg1_refs = (
            f"{msg1_data.get('references', '')} {msg1_data.get('in_reply_to', '')}"
        )
        msg2_refs = (
            f"{msg2_data.get('references', '')} {msg2_data.get('in_reply_to', '')}"
        )

        # Check if msg1 references msg2 or vice versa
        return (msg1_id in msg2_refs) or (msg2_id in msg1_refs)

    def _subjects_are_similar(self, subject1: str, subject2: str) -> bool:
        """Check if two subjects are similar enough to be in same thread."""
        norm1 = self._normalize_subject(subject1)
        norm2 = self._normalize_subject(subject2)

        # Exact match after normalization
        if norm1 == norm2:
            return True

        # Check if one is a subset of the other (allowing for truncation)
        if norm1 in norm2 or norm2 in norm1:
            return True

        return False
