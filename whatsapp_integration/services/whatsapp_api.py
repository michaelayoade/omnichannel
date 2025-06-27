import logging
import time
from datetime import datetime, timedelta
from typing import Any, ClassVar

import requests
from django.core.files.base import ContentFile
from django.utils import timezone

from ..cache import (
    get_cached_rate_limit,
    update_rate_limit_cache,
)
from ..models import (
    WhatsAppBusinessAccount,
    WhatsAppContact,
    WhatsAppMediaFile,
    WhatsAppMessage,
    WhatsAppRateLimit,
)
from ..utils.phone_validator import PhoneNumberValidator

logger = logging.getLogger(__name__)


class WhatsAppAPIError(Exception):
    """Custom exception for WhatsApp API errors."""

    def __init__(self, message: str, error_code: str | None = None, status_code: int | None = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class RateLimitExceeded(WhatsAppAPIError):
    """Exception raised when API rate limit is exceeded."""

    pass


class WhatsAppBusinessAPI:
    """WhatsApp Business API client for sending and receiving messages.
    
    Handles rate limiting, retries, and error handling.
    """

    # API Constants
    BASE_URL: ClassVar[str] = "https://graph.facebook.com/v18.0"

    # HTTP Status Codes
    HTTP_STATUS_RATE_LIMITED: int = 429
    HTTP_STATUS_OK: int = 200

    # Retry Parameters
    DEFAULT_RETRY_AFTER: int = 60  # seconds
    DEFAULT_MAX_RETRIES: int = 3
    EXPONENTIAL_BACKOFF_BASE: int = 2  # for 2^n backoff

    def __init__(self, business_account: WhatsAppBusinessAccount):
        self.business_account = business_account
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {business_account.access_token}",
                "Content-Type": "application/json",
            },
        )

    def _check_rate_limit(self, endpoint: str) -> bool:
        """Check if rate limit allows request using Redis cache when available."""
        now = timezone.now()

        # Check per-second rate limit
        second_window_start = now.replace(microsecond=0)
        second_window_end = second_window_start + timedelta(seconds=1)

        # Check cache first for better performance
        cached_limit = get_cached_rate_limit(self.business_account, f"{endpoint}:second")

        if cached_limit:
            # Use cached data
            if cached_limit["is_blocked"]:
                return False

            request_count = cached_limit["request_count"]
            if request_count >= self.business_account.rate_limit_per_second:
                # Update cache to block requests
                update_rate_limit_cache(
                    self.business_account,
                    f"{endpoint}:second",
                    request_count,
                    second_window_start,
                    second_window_end,
                    is_blocked=True,
                )
                return False
        else:
            # Fall back to database
            second_limit, created = WhatsAppRateLimit.objects.get_or_create(
                business_account=self.business_account,
                endpoint=endpoint,
                window_start=second_window_start,
                defaults={"window_end": second_window_end, "request_count": 0},
            )

        if second_limit.request_count >= self.business_account.rate_limit_per_second:
            return False

        # Check per-hour rate limit
        hour_window_start = now.replace(minute=0, second=0, microsecond=0)
        hour_window_end = hour_window_start + timedelta(hours=1)

        # Check cache first for better performance
        cached_hourly_limit = get_cached_rate_limit(self.business_account, f"{endpoint}:hourly")

        if cached_hourly_limit:
            # Use cached data
            if cached_hourly_limit["is_blocked"]:
                return False

            request_count = cached_hourly_limit["request_count"]
            if request_count >= self.business_account.rate_limit_per_hour:
                # Update cache to block requests
                update_rate_limit_cache(
                    self.business_account,
                    f"{endpoint}:hourly",
                    request_count,
                    hour_window_start,
                    hour_window_end,
                    is_blocked=True,
                )
                return False
        else:
            # Fall back to database
            hour_limit, created = WhatsAppRateLimit.objects.get_or_create(
                business_account=self.business_account,
                endpoint=f"{endpoint}_hourly",
                window_start=hour_window_start,
                defaults={"window_end": hour_window_end, "request_count": 0},
            )

        if hour_limit.request_count >= self.business_account.rate_limit_per_hour:
            return False

        return True

    def _increment_rate_limit(self, endpoint: str):
        """Increment rate limit counters with Redis cache support."""
        now = timezone.now()

        # Increment per-second counter
        second_window_start = now.replace(microsecond=0)
        second_window_end = second_window_start + timedelta(seconds=1)

        # Check cache first
        cached_limit = get_cached_rate_limit(self.business_account, f"{endpoint}:second")

        if cached_limit:
            # Update cached counter
            request_count = cached_limit["request_count"] + 1

            # Update cache
            update_rate_limit_cache(
                self.business_account,
                f"{endpoint}:second",
                request_count,
                second_window_start,
                second_window_end,
                is_blocked=request_count >= self.business_account.rate_limit_per_second,
            )

            # Periodically sync to database to ensure persistence
            if request_count % 10 == 0:  # Every 10 requests
                second_limit, created = WhatsAppRateLimit.objects.get_or_create(
                    business_account=self.business_account,
                    endpoint=endpoint,
                    window_start=second_window_start,
                    defaults={"window_end": second_window_end, "request_count": request_count},
                )

                if not created:
                    second_limit.request_count = request_count
                    second_limit.save()
        else:
            # Fall back to database
            second_limit, created = WhatsAppRateLimit.objects.get_or_create(
                business_account=self.business_account,
                endpoint=endpoint,
                window_start=second_window_start,
                defaults={"window_end": second_window_end},
            )

            second_limit.request_count += 1
            second_limit.save()

            # Update cache after database update
            update_rate_limit_cache(
                self.business_account,
                f"{endpoint}:second",
                second_limit.request_count,
                second_window_start,
                second_window_end,
                is_blocked=second_limit.request_count >= self.business_account.rate_limit_per_second,
            )

        # Increment per-hour counter
        hour_window_start = now.replace(minute=0, second=0, microsecond=0)
        hour_window_end = hour_window_start + timedelta(hours=1)

        # Check hourly cache
        cached_hourly_limit = get_cached_rate_limit(self.business_account, f"{endpoint}:hourly")

        if cached_hourly_limit:
            # Update cached counter
            hourly_request_count = cached_hourly_limit["request_count"] + 1

            # Update cache
            update_rate_limit_cache(
                self.business_account,
                f"{endpoint}:hourly",
                hourly_request_count,
                hour_window_start,
                hour_window_end,
                is_blocked=hourly_request_count >= self.business_account.rate_limit_per_hour,
            )

            # Periodically sync to database (less frequently for hourly metrics)
            if hourly_request_count % 50 == 0:  # Every 50 requests
                hour_limit, created = WhatsAppRateLimit.objects.get_or_create(
                    business_account=self.business_account,
                    endpoint=f"{endpoint}_hourly",
                    window_start=hour_window_start,
                    defaults={"window_end": hour_window_end, "request_count": hourly_request_count},
                )

                if not created:
                    hour_limit.request_count = hourly_request_count
                    hour_limit.save()
        else:
            # Fall back to database
            hour_limit, created = WhatsAppRateLimit.objects.get_or_create(
                business_account=self.business_account,
                endpoint=f"{endpoint}_hourly",
                window_start=hour_window_start,
                defaults={"window_end": hour_window_end},
            )

            hour_limit.request_count += 1
            hour_limit.save()

            # Update cache after database update
            update_rate_limit_cache(
                self.business_account,
                f"{endpoint}:hourly",
                hour_limit.request_count,
                hour_window_start,
                hour_window_end,
                is_blocked=hour_limit.request_count >= self.business_account.rate_limit_per_hour,
            )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> dict[str, Any]:
        """Make HTTP request with rate limiting and retries."""
        if not self._check_rate_limit(endpoint):
            raise RateLimitExceeded("Rate limit exceeded")

        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(max_retries + 1):
            try:
                self._increment_rate_limit(endpoint)

                if method.upper() == "GET":
                    response = self.session.get(url, params=data)
                elif method.upper() == "POST":
                    if files:
                        response = self.session.post(url, data=data, files=files)
                    else:
                        response = self.session.post(url, json=data)  # nosec B113
                elif method.upper() == "DELETE":
                    response = self.session.delete(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Handle rate limiting
                if response.status_code == self.HTTP_STATUS_RATE_LIMITED:
                    retry_after = int(response.headers.get("Retry-After", self.DEFAULT_RETRY_AFTER))
                    if attempt < max_retries:
                        logger.warning(f"Rate limited, retrying after {retry_after}s")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitExceeded("Rate limit exceeded after retries")

                # Handle other errors
                if not response.ok:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get(
                        "message", "Unknown error",
                    )
                    error_code = error_data.get("error", {}).get("code")

                    raise WhatsAppAPIError(
                        message=error_message,
                        error_code=str(error_code),
                        status_code=response.status_code,
                    )

                return response.json()

            except requests.RequestException as e:
                if attempt < max_retries:
                    wait_time = self.EXPONENTIAL_BACKOFF_BASE**attempt  # Exponential backoff
                    logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise WhatsAppAPIError(
                    f"Request failed after {max_retries} retries: {e}",
                ) from e

        raise WhatsAppAPIError("Max retries exceeded")

    def send_text_message(self, to: str, text: str, preview_url: bool = False) -> dict:
        """Send a text message."""
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }

        return self._make_request(
            "POST", f"{self.business_account.phone_number_id}/messages", data,
        )

    def send_media_message(
        self,
        to: str,
        media_type: str,
        media_id: str | None = None,
        media_url: str | None = None,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict:
        """Send a media message (image, audio, video, document)."""
        if not media_id and not media_url:
            raise ValueError("Either media_id or media_url must be provided")

        media_object = {}
        if media_id:
            media_object["id"] = media_id
        else:
            media_object["link"] = media_url

        if caption:
            media_object["caption"] = caption

        if filename and media_type == "document":
            media_object["filename"] = filename

        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_object,
        }

        return self._make_request(
            "POST", f"{self.business_account.phone_number_id}/messages", data,
        )

    def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US",
        components: list[dict] | None = None,
    ) -> dict:
        """Send a template message."""
        template_data = {"name": template_name, "language": {"code": language_code}}

        if components:
            template_data["components"] = components

        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template_data,
        }

        return self._make_request(
            "POST", f"{self.business_account.phone_number_id}/messages", data,
        )

    def send_interactive_message(self, to: str, interactive_data: dict) -> dict:
        """Send an interactive message (buttons, list, etc.)."""
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive_data,
        }

        return self._make_request(
            "POST", f"{self.business_account.phone_number_id}/messages", data,
        )

    def upload_media(self, file_path: str, media_type: str) -> str:
        """Upload media file and return media ID."""
        with open(file_path, "rb") as f:
            files = {"file": f, "type": media_type, "messaging_product": "whatsapp"}

            response = self._make_request(
                "POST", f"{self.business_account.phone_number_id}/media", files=files,
            )

            return response["id"]

    def download_media(self, media_id: str) -> tuple[bytes, str, str]:
        """Download media file by ID. Returns (content, filename, mime_type)."""
        # Get media URL
        media_info = self._make_request("GET", media_id)
        media_url = media_info["url"]
        mime_type = media_info.get("mime_type", "application/octet-stream")

        # Download media content
        response = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {self.business_account.access_token}"},
            timeout=10,
        )
        response.raise_for_status()

        # Extract filename from content-disposition or use media_id
        filename = media_id
        if "content-disposition" in response.headers:
            import re

            match = re.search(
                r'filename="([^"]+)"', response.headers["content-disposition"],
            )
            if match:
                filename = match.group(1)

        return response.content, filename, mime_type

    def mark_message_as_read(self, message_id: str) -> dict:
        """Mark a message as read."""
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        return self._make_request(
            "POST", f"{self.business_account.phone_number_id}/messages", data,
        )

    def get_business_profile(self) -> dict:
        """Get business profile information."""
        return self._make_request(
            "GET",
            f"{self.business_account.phone_number_id}",
            {"fields": "verified_name,code_verification_status,display_phone_number"},
        )

    def get_templates(self) -> list[dict]:
        """Get all message templates."""
        response = self._make_request(
            "GET", f"{self.business_account.business_account_id}/message_templates",
        )
        return response.get("data", [])

    def create_template(
        self, name: str, category: str, components: list[dict], language: str = "en_US",
    ) -> dict:
        """Create a new message template."""
        data = {
            "name": name,
            "category": category,
            "components": components,
            "language": language,
        }

        return self._make_request(
            "POST",
            f"{self.business_account.business_account_id}/message_templates",
            data,
        )

    def delete_template(self, template_name: str) -> dict:
        """Delete a message template."""
        return self._make_request(
            "DELETE",
            f"{self.business_account.business_account_id}/message_templates",
            {"name": template_name},
        )


class WhatsAppMessageService:
    """Service for handling WhatsApp messages and integration with Django models."""

    def __init__(self, business_account: WhatsAppBusinessAccount):
        self.business_account = business_account
        self.api = WhatsAppBusinessAPI(business_account)

    def send_message(
        self,
        to: str,
        message_type: str,
        content: str | None = None,
        media_id: str | None = None,
        media_url: str | None = None,
        template_name: str | None = None,
        template_components: list[dict] | None = None,
        interactive_data: dict | None = None,
    ) -> WhatsAppMessage:
        """Send a message and create a database record."""
        # Validate and format phone number
        formatted_phone = PhoneNumberValidator.format_for_whatsapp(to)
        if not formatted_phone:
            raise ValueError(f"Invalid phone number: {to}")

        # Get or create contact
        contact, created = WhatsAppContact.objects.get_or_create(
            business_account=self.business_account,
            wa_id=formatted_phone,
            defaults={"phone_number": formatted_phone, "profile_name": ""},
        )

        # Create message record
        message = WhatsAppMessage.objects.create(
            business_account=self.business_account,
            contact=contact,
            wa_message_id="",  # Will be updated after sending
            direction="outbound",
            message_type=message_type,
            content=content or "",
            media_id=media_id or "",
            media_url=media_url or "",
            timestamp=timezone.now(),
            status="pending",
        )

        try:
            # Send message based on type
            if message_type == "text":
                response = self.api.send_text_message(formatted_phone, content)
            elif message_type in ["image", "audio", "video", "document"]:
                response = self.api.send_media_message(
                    formatted_phone, message_type, media_id, media_url, content,
                )
            elif message_type == "template":
                response = self.api.send_template_message(
                    formatted_phone, template_name, "en_US", template_components,
                )
            elif message_type == "interactive":
                response = self.api.send_interactive_message(
                    formatted_phone, interactive_data,
                )
            else:
                raise ValueError(f"Unsupported message type: {message_type}")

            # Update message with response data
            message.wa_message_id = response["messages"][0]["id"]
            message.status = "sent"
            message.sent_at = timezone.now()
            message.raw_payload = response
            message.save()

            logger.info(f"Message sent successfully: {message.wa_message_id}")
            return message

        except Exception as e:
            # Update message with error
            message.status = "failed"
            message.failed_at = timezone.now()
            message.error_message = str(e)
            if isinstance(e, WhatsAppAPIError):
                message.error_code = e.error_code or "api_error"
            message.save()

            logger.error(f"Failed to send message: {e}")
            raise

    def process_incoming_message(self, webhook_data: dict) -> WhatsAppMessage | None:
        """Process incoming message from webhook."""
        try:
            entry = webhook_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            if "messages" not in value:
                return None

            message_data = value["messages"][0]
            contact_data = value.get("contacts", [{}])[0]

            # Get or create contact
            wa_id = message_data["from"]
            contact, created = WhatsAppContact.objects.get_or_create(
                business_account=self.business_account,
                wa_id=wa_id,
                defaults={
                    "phone_number": wa_id,
                    "profile_name": contact_data.get("profile", {}).get("name", ""),
                },
            )

            # Update contact profile if needed
            if not created and contact_data.get("profile", {}).get("name"):
                contact.profile_name = contact_data["profile"]["name"]
                contact.last_message_at = timezone.now()
                contact.save()

            # Create message record
            message = WhatsAppMessage.objects.create(
                business_account=self.business_account,
                contact=contact,
                wa_message_id=message_data["id"],
                direction="inbound",
                message_type=message_data["type"],
                content=self._extract_message_content(message_data),
                timestamp=datetime.fromtimestamp(
                    int(message_data["timestamp"]), tz=timezone.utc,
                ),
                status="delivered",
                delivered_at=timezone.now(),
                raw_payload=message_data,
            )

            # Process media if present
            if message_data["type"] in [
                "image",
                "audio",
                "video",
                "document",
                "sticker",
            ]:
                self._process_media_message(message, message_data)

            logger.info(f"Processed incoming message: {message.wa_message_id}")
            return message

        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
            return None

    def _extract_message_content(self, message_data: dict) -> str:
        """Extract text content from message data."""
        message_type = message_data["type"]

        if message_type == "text":
            return message_data["text"]["body"]
        elif message_type in ["image", "video", "document"]:
            return message_data[message_type].get("caption", "")
        elif message_type == "location":
            location = message_data["location"]
            return f"Location: {location.get('latitude')}, {location.get('longitude')}"
        elif message_type == "contacts":
            contacts = message_data["contacts"]
            contact_name = contacts[0].get('name', {}).get('formatted_name', 'Unknown')
            return f"Contact: {contact_name}"

        return ""

    def _process_media_message(self, message: WhatsAppMessage, message_data: dict):
        """Process and download media from incoming message."""
        message_type = message_data["type"]
        media_data = message_data[message_type]

        media_id = media_data["id"]

        try:
            # Download media
            content, filename, mime_type = self.api.download_media(media_id)

            # Create media file record
            media_file = WhatsAppMediaFile.objects.create(
                business_account=self.business_account,
                message=message,
                media_id=media_id,
                filename=filename,
                mime_type=mime_type,
                file_size=len(content),
                sha256=media_data.get("sha256", ""),
                is_downloaded=True,
            )

            # Save file
            file_content = ContentFile(content, name=filename)
            media_file.file_path.save(filename, file_content)

            # Update message with media info
            message.media_id = media_id
            message.media_filename = filename
            message.media_mime_type = mime_type
            message.media_size = len(content)
            message.media_sha256 = media_data.get("sha256", "")
            message.save()

            logger.info(f"Downloaded media file: {filename}")

        except Exception as e:
            logger.error(f"Error downloading media {media_id}: {e}")

    def update_message_status(self, webhook_data: dict):
        """Update message status from webhook."""
        try:
            entry = webhook_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            if "statuses" not in value:
                return

            for status_data in value["statuses"]:
                message_id = status_data["id"]
                status = status_data["status"]
                timestamp = datetime.fromtimestamp(
                    int(status_data["timestamp"]), tz=timezone.utc,
                )

                try:
                    message = WhatsAppMessage.objects.get(wa_message_id=message_id)
                    message.status = status

                    if status == "sent":
                        message.sent_at = timestamp
                    elif status == "delivered":
                        message.delivered_at = timestamp
                    elif status == "read":
                        message.read_at = timestamp
                    elif status == "failed":
                        message.failed_at = timestamp
                        message.error_code = status_data.get("errors", [{}])[0].get(
                            "code", "",
                        )
                        message.error_message = status_data.get("errors", [{}])[0].get(
                            "title", "",
                        )

                    message.save()
                    logger.info(f"Updated message {message_id} status to {status}")

                except WhatsAppMessage.DoesNotExist:
                    logger.warning(f"Message not found for status update: {message_id}")

        except Exception as e:
            logger.error(f"Error updating message status: {e}")
