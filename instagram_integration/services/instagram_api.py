import logging

import requests
from django.utils import timezone

from ..models import (
    InstagramAccount,
    InstagramMessage,
    InstagramRateLimit,
    InstagramUser,
)

logger = logging.getLogger(__name__)


class InstagramAPIError(Exception):
    """Custom exception for Instagram API errors."""

    pass


class InstagramAPIClient:
    """Instagram Graph API client for DM operations."""

    BASE_URL = "https://graph.instagram.com"
    GRAPH_API_VERSION = "v21.0"

    def __init__(self, account: InstagramAccount):
        self.account = account
        self.access_token = account.access_token
        self.base_url = f"https://graph.facebook.com/{self.GRAPH_API_VERSION}"

    def _make_request(
        self, method: str, endpoint: str, params: dict | None = None, data: dict | None = None,
    ) -> dict:
        """Make authenticated request to Instagram Graph API."""
        url = f"{self.base_url}/{endpoint}"

        # Check rate limiting
        rate_limit = self._check_rate_limit(endpoint)
        if not rate_limit.can_make_call():
            wait_time = rate_limit.get_wait_time()
            raise InstagramAPIError(f"Rate limit exceeded. Wait {wait_time} seconds.")

        # Prepare request parameters
        if params is None:
            params = {}
        params["access_token"] = self.access_token

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, json=data, timeout=30)
            else:
                raise InstagramAPIError(f"Unsupported HTTP method: {method}")

            # Record the API call
            rate_limit.record_call()

            # Handle response
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get("error", {}).get(
                    "message", "Unknown error",
                )
                logger.error(
                    f"Instagram API error: {response.status_code} - {error_message}",
                )
                raise InstagramAPIError(f"API error: {error_message}")

        except requests.RequestException as e:
            logger.error(f"Request error: {e!s}")
            raise InstagramAPIError(f"Request failed: {e!s}")

    def _check_rate_limit(self, endpoint: str) -> InstagramRateLimit:
        """Check and get rate limit for endpoint."""
        rate_limit, created = InstagramRateLimit.objects.get_or_create(
            account=self.account,
            endpoint=endpoint,
            defaults={
                "call_limit": 100,  # Default Instagram API limit
                "window_minutes": 60,
                "reset_time": timezone.now() + timezone.timedelta(hours=1),
            },
        )
        return rate_limit

    def get_account_info(self) -> dict:
        """Get Instagram business account information."""
        endpoint = f"{self.account.instagram_business_account_id}"
        params = {
            "fields": "id,username,name,biography,website,followers_count,profile_picture_url",
        }
        return self._make_request("GET", endpoint, params=params)

    def get_user_profile(self, instagram_user_id: str) -> dict:
        """Get Instagram user profile information."""
        endpoint = f"{instagram_user_id}"
        params = {"fields": "id,username,name,profile_picture_url"}
        return self._make_request("GET", endpoint, params=params)

    def send_message(self, recipient_id: str, message_data: dict) -> dict:
        """Send a direct message to an Instagram user."""
        endpoint = f"{self.account.instagram_business_account_id}/messages"

        data = {"recipient": {"id": recipient_id}, "message": message_data}

        return self._make_request("POST", endpoint, data=data)

    def send_text_message(self, recipient_id: str, text: str) -> dict:
        """Send a text message."""
        message_data = {"text": text}
        return self.send_message(recipient_id, message_data)

    def send_image_message(self, recipient_id: str, image_url: str) -> dict:
        """Send an image message."""
        message_data = {"attachment": {"type": "image", "payload": {"url": image_url}}}
        return self.send_message(recipient_id, message_data)

    def send_video_message(self, recipient_id: str, video_url: str) -> dict:
        """Send a video message."""
        message_data = {"attachment": {"type": "video", "payload": {"url": video_url}}}
        return self.send_message(recipient_id, message_data)

    def get_conversations(self, limit: int = 50) -> dict:
        """Get list of conversations for the Instagram account."""
        endpoint = f"{self.account.instagram_business_account_id}/conversations"
        params = {
            "fields": "id,participants,updated_time,message_count",
            "limit": limit,
        }
        return self._make_request("GET", endpoint, params=params)

    def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> dict:
        """Get messages from a specific conversation."""
        endpoint = f"{conversation_id}/messages"
        params = {
            "fields": "id,from,to,created_time,message,attachments,story",
            "limit": limit,
        }
        return self._make_request("GET", endpoint, params=params)

    def subscribe_webhook(
        self, webhook_url: str, verify_token: str, fields: list[str] | None = None,
    ) -> dict:
        """Subscribe to Instagram webhook events."""
        if fields is None:
            fields = ["messages", "messaging_seen", "story_insights"]

        endpoint = f"{self.account.facebook_page_id}/subscribed_apps"
        data = {
            "subscribed_fields": ",".join(fields),
            "callback_url": webhook_url,
            "verify_token": verify_token,
        }
        return self._make_request("POST", endpoint, data=data)

    def verify_webhook(
        self, verify_token: str, challenge: str, hub_verify_token: str,
    ) -> str | None:
        """Verify webhook subscription."""
        if verify_token == hub_verify_token:
            return challenge
        return None

    def health_check(self) -> tuple[bool, str]:
        """Perform health check on the Instagram account."""
        try:
            account_info = self.get_account_info()

            # Update account information
            self.account.username = account_info.get("username", self.account.username)
            self.account.name = account_info.get("name", self.account.name)
            self.account.biography = account_info.get(
                "biography", self.account.biography,
            )
            self.account.website = account_info.get("website", self.account.website)
            self.account.followers_count = account_info.get("followers_count", 0)
            self.account.profile_picture_url = account_info.get(
                "profile_picture_url", "",
            )

            # Update status
            self.account.status = "active"
            self.account.update_health_status(True)
            self.account.save()

            return True, "Account healthy"

        except InstagramAPIError as e:
            error_message = str(e)
            self.account.status = "error"
            self.account.update_health_status(False, error_message)
            logger.error(
                f"Health check failed for {self.account.username}: {error_message}",
            )
            return False, error_message


class InstagramMessageService:
    """Service for handling Instagram message operations."""

    def __init__(self, account: InstagramAccount):
        self.account = account
        self.api_client = InstagramAPIClient(account)

    def send_text_message(
        self, instagram_user: InstagramUser, text: str,
    ) -> InstagramMessage:
        """Send a text message and create database record."""
        # Create message record
        message = InstagramMessage.objects.create(
            message_id=f"out_{timezone.now().timestamp()}",
            account=self.account,
            instagram_user=instagram_user,
            message_type="text",
            direction="outbound",
            text=text,
            timestamp=timezone.now(),
        )

        try:
            # Send via API
            response = self.api_client.send_text_message(
                instagram_user.instagram_user_id, text,
            )

            # Update message with Instagram ID
            instagram_message_id = response.get("message_id")
            message.mark_as_sent(instagram_message_id)

            # Update statistics
            self.account.total_messages_sent += 1
            self.account.save(update_fields=["total_messages_sent"])

            instagram_user.total_messages_sent += 1
            instagram_user.update_last_interaction()
            instagram_user.save(update_fields=["total_messages_sent"])

            logger.info(f"Text message sent to {instagram_user.display_name}")
            return message

        except InstagramAPIError as e:
            message.mark_as_failed(error_message=str(e))
            logger.error(f"Failed to send message: {e!s}")
            raise

    def send_image_message(
        self, instagram_user: InstagramUser, image_url: str,
    ) -> InstagramMessage:
        """Send an image message and create database record."""
        # Create message record
        message = InstagramMessage.objects.create(
            message_id=f"out_{timezone.now().timestamp()}",
            account=self.account,
            instagram_user=instagram_user,
            message_type="image",
            direction="outbound",
            media_url=image_url,
            media_type="image",
            timestamp=timezone.now(),
        )

        try:
            # Send via API
            response = self.api_client.send_image_message(
                instagram_user.instagram_user_id, image_url,
            )

            # Update message with Instagram ID
            instagram_message_id = response.get("message_id")
            message.mark_as_sent(instagram_message_id)

            # Update statistics
            self.account.total_messages_sent += 1
            self.account.save(update_fields=["total_messages_sent"])

            instagram_user.total_messages_sent += 1
            instagram_user.update_last_interaction()
            instagram_user.save(update_fields=["total_messages_sent"])

            logger.info(f"Image message sent to {instagram_user.display_name}")
            return message

        except InstagramAPIError as e:
            message.mark_as_failed(error_message=str(e))
            logger.error(f"Failed to send image: {e!s}")
            raise

    def get_or_create_user(self, instagram_user_id: str) -> InstagramUser:
        """Get or create Instagram user profile."""
        user, created = InstagramUser.objects.get_or_create(
            instagram_user_id=instagram_user_id, account=self.account,
        )

        if created:
            try:
                # Fetch user profile from API
                profile_data = self.api_client.get_user_profile(instagram_user_id)
                user.username = profile_data.get("username", "")
                user.name = profile_data.get("name", "")
                user.profile_picture_url = profile_data.get("profile_picture_url", "")
                user.save()
                logger.info(f"Created new Instagram user: {user.display_name}")
            except InstagramAPIError as e:
                logger.warning(
                    f"Could not fetch profile for {instagram_user_id}: {e!s}",
                )

        return user

    def process_incoming_message(self, message_data: dict) -> InstagramMessage:
        """Process incoming message from webhook."""
        sender_id = message_data.get("from", {}).get("id")
        message_id = message_data.get("id")
        timestamp = message_data.get("created_time")

        # Get or create user
        instagram_user = self.get_or_create_user(sender_id)

        # Determine message type and content
        message_type = "text"
        text = ""
        media_url = ""
        media_type = ""
        story_id = ""

        if "message" in message_data:
            text = message_data["message"]
        elif "attachments" in message_data:
            attachment = message_data["attachments"][0]
            if attachment.get("type") == "image":
                message_type = "image"
                media_url = attachment.get("payload", {}).get("url", "")
                media_type = "image"
            elif attachment.get("type") == "video":
                message_type = "video"
                media_url = attachment.get("payload", {}).get("url", "")
                media_type = "video"
        elif "story" in message_data:
            message_type = "story_reply"
            story_id = message_data["story"].get("id", "")
            text = message_data.get("text", "")

        # Create message record
        message = InstagramMessage.objects.create(
            message_id=message_id,
            instagram_message_id=message_id,
            account=self.account,
            instagram_user=instagram_user,
            message_type=message_type,
            direction="inbound",
            status="delivered",
            text=text,
            media_url=media_url,
            media_type=media_type,
            story_id=story_id,
            timestamp=timezone.datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
            payload=message_data,
        )

        # Update statistics
        self.account.total_messages_received += 1
        self.account.save(update_fields=["total_messages_received"])

        instagram_user.total_messages_received += 1
        instagram_user.update_last_interaction()
        instagram_user.save(update_fields=["total_messages_received"])

        logger.info(
            f"Processed incoming {message_type} from {instagram_user.display_name}",
        )
        return message
