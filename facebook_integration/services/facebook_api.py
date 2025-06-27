import hashlib
import hmac
import json
import logging
import time

import requests
from django.utils import timezone

from ..models import FacebookMessage, FacebookPage, FacebookTemplate, FacebookUser

logger = logging.getLogger(__name__)


class FacebookGraphAPI:
    """Facebook Graph API client for Messenger operations."""

    BASE_URL = "https://graph.facebook.com/v18.0"
    MESSENGER_PROFILE_URL = "https://graph.facebook.com/v18.0/me/messenger_profile"

    def __init__(self, page: FacebookPage):
        self.page = page
        self.access_token = page.page_access_token
        self.app_secret = page.app_secret

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        files: dict | None = None,
        timeout: int = 30,
    ) -> tuple[bool, dict]:
        """Make a request to Facebook Graph API with error handling."""
        url = f"{self.BASE_URL}/{endpoint}"

        # Add access token to parameters
        params = {"access_token": self.access_token}
        if method.upper() == "GET" and data:
            params.update(data)
            data = None

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=timeout)
            elif method.upper() == "POST":
                if files:
                    response = requests.post(
                        url, params=params, data=data, files=files, timeout=timeout,
                    )
                else:
                    headers = {"Content-Type": "application/json"}
                    response = requests.post(
                        url,
                        params=params,
                        data=json.dumps(data) if data else None,
                        headers=headers,
                        timeout=timeout,
                    )
            elif method.upper() == "DELETE":
                response = requests.delete(url, params=params, timeout=timeout)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            response.raise_for_status()
            return True, response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Facebook API request failed: {e}")
            error_detail = {}

            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = {"error": str(e)}
            else:
                error_detail = {"error": str(e)}

            return False, error_detail

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify webhook signature from Facebook."""
        if not signature.startswith("sha1="):
            return False

        expected_signature = hmac.new(
            self.app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1,
        ).hexdigest()

        return hmac.compare_digest(signature[5:], expected_signature)

    def send_text_message(
        self, recipient_id: str, text: str, quick_replies: list[dict] | None = None,
    ) -> tuple[bool, dict]:
        """Send a text message to a user."""
        message_data = {"recipient": {"id": recipient_id}, "message": {"text": text}}

        if quick_replies:
            message_data["message"]["quick_replies"] = quick_replies

        return self._make_request("POST", "me/messages", message_data)

    def send_attachment(
        self,
        recipient_id: str,
        attachment_type: str,
        attachment_url: str | None = None,
        attachment_id: str | None = None,
        is_reusable: bool = False,
    ) -> tuple[bool, dict]:
        """Send an attachment (image, video, audio, file)."""
        message_data = {
            "recipient": {"id": recipient_id},
            "message": {"attachment": {"type": attachment_type}},
        }

        if attachment_url:
            message_data["message"]["attachment"]["payload"] = {
                "url": attachment_url,
                "is_reusable": is_reusable,
            }
        elif attachment_id:
            message_data["message"]["attachment"]["payload"] = {
                "attachment_id": attachment_id,
            }
        else:
            return False, {
                "error": "Either attachment_url or attachment_id must be provided",
            }

        return self._make_request("POST", "me/messages", message_data)

    def upload_attachment(
        self, file_url: str, attachment_type: str,
    ) -> tuple[bool, dict]:
        """Upload an attachment and get reusable attachment ID."""
        data = {
            "message": {
                "attachment": {
                    "type": attachment_type,
                    "payload": {"url": file_url, "is_reusable": True},
                },
            },
        }

        return self._make_request("POST", "me/message_attachments", data)

    def send_template_message(
        self, recipient_id: str, template_data: dict,
    ) -> tuple[bool, dict]:
        """Send a template message (button, generic, list, etc.)."""
        message_data = {
            "recipient": {"id": recipient_id},
            "message": {"attachment": {"type": "template", "payload": template_data}},
        }

        return self._make_request("POST", "me/messages", message_data)

    def send_button_template(
        self, recipient_id: str, text: str, buttons: list[dict],
    ) -> tuple[bool, dict]:
        """Send a button template message."""
        template_data = {"template_type": "button", "text": text, "buttons": buttons}

        return self.send_template_message(recipient_id, template_data)

    def send_generic_template(
        self, recipient_id: str, elements: list[dict],
    ) -> tuple[bool, dict]:
        """Send a generic template (carousel) message."""
        template_data = {"template_type": "generic", "elements": elements}

        return self.send_template_message(recipient_id, template_data)

    def send_list_template(
        self,
        recipient_id: str,
        elements: list[dict],
        top_element_style: str = "compact",
        buttons: list[dict] | None = None,
    ) -> tuple[bool, dict]:
        """Send a list template message."""
        template_data = {
            "template_type": "list",
            "top_element_style": top_element_style,
            "elements": elements,
        }

        if buttons:
            template_data["buttons"] = buttons

        return self.send_template_message(recipient_id, template_data)

    def get_user_profile(
        self,
        user_id: str,
        fields: str = "first_name,last_name,profile_pic,locale,timezone,gender",
    ) -> tuple[bool, dict]:
        """Get user profile information."""
        return self._make_request("GET", user_id, {"fields": fields})

    def set_messenger_profile(self, profile_data: dict) -> tuple[bool, dict]:
        """Set Messenger profile (persistent menu, greeting, etc.)."""
        return self._make_request("POST", "me/messenger_profile", profile_data)

    def get_messenger_profile(self, fields: str | None = None) -> tuple[bool, dict]:
        """Get current Messenger profile settings."""
        params = {}
        if fields:
            params["fields"] = fields
        return self._make_request("GET", "me/messenger_profile", params)

    def delete_messenger_profile(self, fields: list[str]) -> tuple[bool, dict]:
        """Delete specific Messenger profile fields."""
        data = {"fields": fields}
        return self._make_request("DELETE", "me/messenger_profile", data)

    def set_get_started_button(self, payload: str = "GET_STARTED") -> tuple[bool, dict]:
        """Set the Get Started button."""
        data = {"get_started": {"payload": payload}}
        return self.set_messenger_profile(data)

    def set_persistent_menu(
        self, menu_items: list[dict], composer_input_disabled: bool = False,
    ) -> tuple[bool, dict]:
        """Set persistent menu."""
        data = {
            "persistent_menu": [
                {
                    "locale": "default",
                    "composer_input_disabled": composer_input_disabled,
                    "call_to_actions": menu_items,
                },
            ],
        }
        return self.set_messenger_profile(data)

    def set_greeting_text(self, greeting: str) -> tuple[bool, dict]:
        """Set greeting text."""
        data = {"greeting": [{"locale": "default", "text": greeting}]}
        return self.set_messenger_profile(data)

    def set_ice_breakers(self, ice_breakers: list[dict]) -> tuple[bool, dict]:
        """Set ice breaker questions."""
        data = {"ice_breakers": ice_breakers}
        return self.set_messenger_profile(data)

    def whitelist_domains(self, domains: list[str]) -> tuple[bool, dict]:
        """Whitelist domains for webview."""
        data = {"whitelisted_domains": domains}
        return self.set_messenger_profile(data)

    def pass_thread_control(
        self, recipient_id: str, target_app_id: str, metadata: str | None = None,
    ) -> tuple[bool, dict]:
        """Pass thread control to another app (handover protocol)."""
        data = {"recipient": {"id": recipient_id}, "target_app_id": target_app_id}

        if metadata:
            data["metadata"] = metadata

        return self._make_request("POST", "me/pass_thread_control", data)

    def take_thread_control(
        self, recipient_id: str, metadata: str | None = None,
    ) -> tuple[bool, dict]:
        """Take thread control from another app."""
        data = {"recipient": {"id": recipient_id}}

        if metadata:
            data["metadata"] = metadata

        return self._make_request("POST", "me/take_thread_control", data)

    def request_thread_control(
        self, recipient_id: str, metadata: str | None = None,
    ) -> tuple[bool, dict]:
        """Request thread control from primary receiver."""
        data = {"recipient": {"id": recipient_id}}

        if metadata:
            data["metadata"] = metadata

        return self._make_request("POST", "me/request_thread_control", data)

    def get_secondary_receivers(self) -> tuple[bool, dict]:
        """Get list of secondary receivers for handover protocol."""
        return self._make_request("GET", "me/secondary_receivers")

    def mark_seen(self, recipient_id: str) -> tuple[bool, dict]:
        """Mark message as seen (typing indicator off)."""
        data = {"recipient": {"id": recipient_id}, "sender_action": "mark_seen"}
        return self._make_request("POST", "me/messages", data)

    def typing_on(self, recipient_id: str) -> tuple[bool, dict]:
        """Turn typing indicator on."""
        data = {"recipient": {"id": recipient_id}, "sender_action": "typing_on"}
        return self._make_request("POST", "me/messages", data)

    def typing_off(self, recipient_id: str) -> tuple[bool, dict]:
        """Turn typing indicator off."""
        data = {"recipient": {"id": recipient_id}, "sender_action": "typing_off"}
        return self._make_request("POST", "me/messages", data)


class FacebookMessengerService:
    """High-level service for Facebook Messenger operations."""

    def __init__(self, page: FacebookPage):
        self.page = page
        self.api = FacebookGraphAPI(page)

    def send_message(
        self,
        recipient_psid: str,
        message_type: str = "text",
        content: str | None = None,
        template_data: dict | None = None,
        attachment_url: str | None = None,
        attachment_type: str | None = None,
        quick_replies: list[dict] | None = None,
    ) -> FacebookMessage:
        """Send a message and create a FacebookMessage record."""
        # Get or create user
        facebook_user, created = FacebookUser.objects.get_or_create(
            psid=recipient_psid,
            page=self.page,
            defaults={"last_interaction_at": timezone.now()},
        )

        if created:
            # Fetch user profile if new user
            self._update_user_profile(facebook_user)

        # Create message record
        message = FacebookMessage.objects.create(
            message_id=f"out_{int(time.time() * 1000)}_{recipient_psid}",
            page=self.page,
            facebook_user=facebook_user,
            message_type=message_type,
            direction="outbound",
            text=content or "",
            payload={"template_data": template_data} if template_data else {},
            attachment_url=attachment_url or "",
            attachment_type=attachment_type or "",
        )

        # Send message via API
        success, response = self._send_message_to_api(
            recipient_psid,
            message_type,
            content,
            template_data,
            attachment_url,
            attachment_type,
            quick_replies,
        )

        if success:
            facebook_message_id = response.get("message_id", "")
            message.mark_as_sent(facebook_message_id)

            # Update statistics
            self.page.total_messages_sent += 1
            self.page.save(update_fields=["total_messages_sent"])

            facebook_user.total_messages_sent += 1
            facebook_user.update_last_interaction()

        else:
            error_message = response.get("error", {}).get("message", "Unknown error")
            error_code = response.get("error", {}).get("code", "UNKNOWN")
            message.mark_as_failed(error_code, error_message)

        return message

    def _send_message_to_api(
        self,
        recipient_psid: str,
        message_type: str,
        content: str | None = None,
        template_data: dict | None = None,
        attachment_url: str | None = None,
        attachment_type: str | None = None,
        quick_replies: list[dict] | None = None,
    ) -> tuple[bool, dict]:
        """Send message to Facebook API based on type."""
        if message_type == "text":
            return self.api.send_text_message(recipient_psid, content, quick_replies)

        elif message_type == "template":
            return self.api.send_template_message(recipient_psid, template_data)

        elif message_type in ["image", "video", "audio", "file"]:
            return self.api.send_attachment(
                recipient_psid, message_type, attachment_url,
            )

        else:
            return False, {"error": f"Unsupported message type: {message_type}"}

    def send_text(
        self, recipient_psid: str, text: str, quick_replies: list[dict] | None = None,
    ) -> FacebookMessage:
        """Send a text message."""
        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="text",
            content=text,
            quick_replies=quick_replies,
        )

    def send_image(self, recipient_psid: str, image_url: str) -> FacebookMessage:
        """Send an image."""
        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="image",
            attachment_url=image_url,
            attachment_type="image",
        )

    def send_video(self, recipient_psid: str, video_url: str) -> FacebookMessage:
        """Send a video."""
        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="video",
            attachment_url=video_url,
            attachment_type="video",
        )

    def send_audio(self, recipient_psid: str, audio_url: str) -> FacebookMessage:
        """Send an audio file."""
        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="audio",
            attachment_url=audio_url,
            attachment_type="audio",
        )

    def send_file(self, recipient_psid: str, file_url: str) -> FacebookMessage:
        """Send a file."""
        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="file",
            attachment_url=file_url,
            attachment_type="file",
        )

    def send_button_template(
        self, recipient_psid: str, text: str, buttons: list[dict],
    ) -> FacebookMessage:
        """Send a button template."""
        template_data = {"template_type": "button", "text": text, "buttons": buttons}

        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="template",
            template_data=template_data,
        )

    def send_generic_template(
        self, recipient_psid: str, elements: list[dict],
    ) -> FacebookMessage:
        """Send a generic template (carousel)."""
        template_data = {"template_type": "generic", "elements": elements}

        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="template",
            template_data=template_data,
        )

    def send_quick_reply(
        self, recipient_psid: str, text: str, quick_replies: list[dict],
    ) -> FacebookMessage:
        """Send a message with quick replies."""
        return self.send_text(recipient_psid, text, quick_replies)

    def send_template_message(
        self, recipient_psid: str, template: FacebookTemplate, variables: dict | None = None,
    ) -> FacebookMessage:
        """Send a message using a saved template."""
        # Process template variables
        template_data = template.template_data.copy()
        if variables and template.variables:
            template_data = self._process_template_variables(template_data, variables)

        # Increment template usage
        template.increment_usage()

        return self.send_message(
            recipient_psid=recipient_psid,
            message_type="template",
            template_data=template_data,
        )

    def _process_template_variables(self, template_data: dict, variables: dict) -> dict:
        """Process template variables in template data."""
        # Convert to JSON string, replace variables, then parse back
        template_str = json.dumps(template_data)

        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            template_str = template_str.replace(placeholder, str(var_value))

        return json.loads(template_str)

    def _update_user_profile(self, facebook_user: FacebookUser):
        """Update user profile information from Facebook."""
        success, profile_data = self.api.get_user_profile(facebook_user.psid)

        if success:
            facebook_user.first_name = profile_data.get("first_name", "")
            facebook_user.last_name = profile_data.get("last_name", "")
            facebook_user.profile_pic = profile_data.get("profile_pic", "")
            facebook_user.locale = profile_data.get("locale", "")
            facebook_user.timezone = profile_data.get("timezone")
            facebook_user.gender = profile_data.get("gender", "")
            facebook_user.save()

            # Try to match with existing customer
            self._match_customer(facebook_user)

    def _match_customer(self, facebook_user: FacebookUser):
        """Try to match Facebook user with existing customer."""
        from customers.models import Customer

        if facebook_user.customer:
            return  # Already matched

        full_name = facebook_user.full_name.strip()
        if not full_name:
            return

        # Try to find customer by name
        potential_customers = Customer.objects.filter(full_name__icontains=full_name)

        if potential_customers.count() == 1:
            facebook_user.customer = potential_customers.first()
            facebook_user.save(update_fields=["customer"])

        # Could add more sophisticated matching logic here
        # (email matching, phone matching, etc.)

    def mark_message_delivered(self, facebook_message_id: str):
        """Mark a message as delivered."""
        try:
            message = FacebookMessage.objects.get(
                facebook_message_id=facebook_message_id,
            )
            message.mark_as_delivered()
        except FacebookMessage.DoesNotExist:
            logger.warning(
                f"Message not found for delivery update: {facebook_message_id}",
            )

    def mark_message_read(self, facebook_message_id: str):
        """Mark a message as read."""
        try:
            message = FacebookMessage.objects.get(
                facebook_message_id=facebook_message_id,
            )
            message.mark_as_read()
        except FacebookMessage.DoesNotExist:
            logger.warning(f"Message not found for read update: {facebook_message_id}")

    def set_typing_indicator(self, recipient_psid: str, typing: bool = True):
        """Set typing indicator for user."""
        if typing:
            self.api.typing_on(recipient_psid)
        else:
            self.api.typing_off(recipient_psid)

    def configure_page_settings(self, configuration_data: dict) -> bool:
        """Configure page Messenger profile settings."""
        from ..models import FacebookPageConfiguration

        config, created = FacebookPageConfiguration.objects.get_or_create(
            page=self.page, defaults=configuration_data,
        )

        if not created:
            for key, value in configuration_data.items():
                setattr(config, key, value)
            config.save()

        # Apply settings to Facebook
        success = True

        # Set greeting text
        if config.greeting_text:
            api_success, _ = self.api.set_greeting_text(config.greeting_text)
            success = success and api_success

        # Set get started button
        if config.get_started_payload:
            api_success, _ = self.api.set_get_started_button(config.get_started_payload)
            success = success and api_success

        # Set persistent menu
        if config.persistent_menu:
            api_success, _ = self.api.set_persistent_menu(config.persistent_menu)
            success = success and api_success

        # Set ice breakers
        if config.ice_breakers:
            api_success, _ = self.api.set_ice_breakers(config.ice_breakers)
            success = success and api_success

        # Whitelist domains
        if config.whitelisted_domains:
            api_success, _ = self.api.whitelist_domains(config.whitelisted_domains)
            success = success and api_success

        if success:
            config.mark_as_synced()

        return success

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to Facebook API."""
        try:
            success, response = self.api.get_messenger_profile()

            if success:
                self.page.update_health_status(True)
                return True, "Connection successful"
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                self.page.update_health_status(False, error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = str(e)
            self.page.update_health_status(False, error_msg)
            return False, error_msg


class FacebookRateLimiter:
    """Rate limiter for Facebook API calls."""

    def __init__(self, page: FacebookPage, max_calls_per_hour: int = 1000):
        self.page = page
        self.max_calls_per_hour = max_calls_per_hour
        self.call_history = []

    def can_make_call(self) -> bool:
        """Check if we can make an API call without hitting rate limits."""
        now = time.time()

        # Remove calls older than 1 hour
        self.call_history = [
            call_time for call_time in self.call_history if now - call_time < 3600
        ]

        return len(self.call_history) < self.max_calls_per_hour

    def record_call(self):
        """Record an API call."""
        self.call_history.append(time.time())

    def get_wait_time(self) -> int:
        """Get time to wait before next call (in seconds)."""
        if self.can_make_call():
            return 0

        # Return time until oldest call expires
        now = time.time()
        oldest_call = min(self.call_history)
        return int(3600 - (now - oldest_call))


# Helper functions for creating common message components


def create_quick_reply(title: str, payload: str, image_url: str | None = None) -> dict:
    """Create a quick reply button."""
    quick_reply = {"content_type": "text", "title": title, "payload": payload}

    if image_url:
        quick_reply["image_url"] = image_url

    return quick_reply


def create_postback_button(title: str, payload: str) -> dict:
    """Create a postback button."""
    return {"type": "postback", "title": title, "payload": payload}


def create_url_button(title: str, url: str, webview_height_ratio: str = "tall") -> dict:
    """Create a URL button."""
    return {
        "type": "web_url",
        "title": title,
        "url": url,
        "webview_height_ratio": webview_height_ratio,
    }


def create_call_button(title: str, phone_number: str) -> dict:
    """Create a call button."""
    return {"type": "phone_number", "title": title, "payload": phone_number}


def create_generic_element(
    title: str,
    subtitle: str | None = None,
    image_url: str | None = None,
    default_action: dict | None = None,
    buttons: list[dict] | None = None,
) -> dict:
    """Create a generic template element."""
    element = {"title": title}

    if subtitle:
        element["subtitle"] = subtitle
    if image_url:
        element["image_url"] = image_url
    if default_action:
        element["default_action"] = default_action
    if buttons:
        element["buttons"] = buttons

    return element


def create_list_element(
    title: str, subtitle: str | None = None, image_url: str | None = None, default_action: dict | None = None,
) -> dict:
    """Create a list template element."""
    element = {"title": title}

    if subtitle:
        element["subtitle"] = subtitle
    if image_url:
        element["image_url"] = image_url
    if default_action:
        element["default_action"] = default_action

    return element
