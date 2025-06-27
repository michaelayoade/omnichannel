import hashlib
import hmac
import json
import logging

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..models import (
    InstagramAccount,
    InstagramMessage,
    InstagramStory,
    InstagramWebhookEvent,
)
from ..services import InstagramMessageService

logger = logging.getLogger(__name__)


class InstagramWebhookHandler:
    """Handler for Instagram webhook events."""

    def __init__(self, account: InstagramAccount):
        self.account = account
        self.message_service = InstagramMessageService(account)

    def verify_signature(self, request_body: bytes, signature: str) -> bool:
        """Verify webhook signature for security."""
        if not signature:
            return False

        try:
            expected_signature = hmac.new(
                self.account.app_secret.encode("utf-8"), request_body, hashlib.sha256,
            ).hexdigest()

            # Instagram sends signature as 'sha256=<hash>'
            if signature.startswith("sha256="):
                signature = signature[7:]

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e!s}")
            return False

    def process_webhook_event(self, event_data: dict) -> None:
        """Process incoming webhook event."""
        try:
            # Extract event information
            event_type = self._determine_event_type(event_data)
            event_id = self._generate_event_id(event_data)

            # Create webhook event record
            webhook_event = InstagramWebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                account=self.account,
                raw_data=event_data,
            )

            # Process based on event type
            if event_type == "messages":
                self._process_message_event(webhook_event, event_data)
            elif event_type == "messaging_seen":
                self._process_message_seen_event(webhook_event, event_data)
            elif event_type == "story_insights":
                self._process_story_event(webhook_event, event_data)
            else:
                webhook_event.status = "ignored"
                webhook_event.save()
                logger.info(f"Ignored webhook event type: {event_type}")

        except Exception as e:
            logger.error(f"Error processing webhook event: {e!s}")
            if "webhook_event" in locals():
                webhook_event.mark_as_failed(str(e))

    def _determine_event_type(self, event_data: dict) -> str:
        """Determine the type of webhook event."""
        if "entry" in event_data:
            for entry in event_data["entry"]:
                if "messaging" in entry:
                    for message in entry["messaging"]:
                        if "message" in message:
                            return "messages"
                        elif "read" in message:
                            return "messaging_seen"
                elif "changes" in entry:
                    for change in entry["changes"]:
                        if change.get("field") == "story_insights":
                            return "story_insights"
        return "unknown"

    def _generate_event_id(self, event_data: dict) -> str:
        """Generate unique event ID."""
        # Use timestamp and hash of event data
        timestamp = str(timezone.now().timestamp())
        data_hash = hashlib.sha256(
            json.dumps(event_data, sort_keys=True).encode(),
        ).hexdigest()
        return f"{timestamp}_{data_hash[:8]}"

    def _process_message_event(
        self, webhook_event: InstagramWebhookEvent, event_data: dict,
    ) -> None:
        """Process direct message event."""
        try:
            for entry in event_data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    if "message" in messaging:
                        message_data = messaging["message"]
                        sender_data = messaging.get("sender", {})

                        # Skip if message is from our account
                        if (
                            sender_data.get("id")
                            == self.account.instagram_business_account_id
                        ):
                            continue

                        # Process the message
                        instagram_message = (
                            self.message_service.process_incoming_message(
                                {
                                    "id": message_data.get("mid"),
                                    "from": sender_data,
                                    "created_time": messaging.get("timestamp"),
                                    "message": message_data.get("text", ""),
                                    "attachments": message_data.get("attachments", []),
                                    "story": message_data.get("reply_to", {}).get(
                                        "story", {},
                                    ),
                                },
                            )
                        )

                        # Link webhook event to message
                        webhook_event.instagram_message = instagram_message
                        webhook_event.instagram_user = instagram_message.instagram_user

                        # Mark as processed
                        webhook_event.mark_as_processed(
                            {
                                "message_id": instagram_message.message_id,
                                "message_type": instagram_message.message_type,
                                "sender_id": (
                                    instagram_message.instagram_user.instagram_user_id
                                ),
                            },
                        )

                        logger.info(
                            f"Processed message event: {instagram_message.message_id}",
                        )

        except Exception as e:
            logger.error(f"Error processing message event: {e!s}")
            webhook_event.mark_as_failed(str(e))

    def _process_message_seen_event(
        self, webhook_event: InstagramWebhookEvent, event_data: dict,
    ) -> None:
        """Process message read event."""
        try:
            for entry in event_data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    if "read" in messaging:
                        read_data = messaging["read"]
                        sender_id = messaging.get("sender", {}).get("id")

                        # Find and update messages as read
                        watermark = read_data.get("watermark")
                        if watermark:
                            # Mark messages as read up to watermark timestamp
                            messages = InstagramMessage.objects.filter(
                                account=self.account,
                                instagram_user__instagram_user_id=sender_id,
                                timestamp__lte=timezone.datetime.fromtimestamp(
                                    int(watermark) / 1000, tz=timezone.utc,
                                ),
                                direction="outbound",
                                status__in=["sent", "delivered"],
                            )

                            for message in messages:
                                message.mark_as_read()

                        webhook_event.mark_as_processed(
                            {"sender_id": sender_id, "watermark": watermark},
                        )

                        logger.info(f"Processed message seen event for {sender_id}")

        except Exception as e:
            logger.error(f"Error processing message seen event: {e!s}")
            webhook_event.mark_as_failed(str(e))

    def _process_story_event(
        self, webhook_event: InstagramWebhookEvent, event_data: dict,
    ) -> None:
        """Process story-related event."""
        try:
            for entry in event_data.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "story_insights":
                        story_data = change.get("value", {})

                        # Create or update story record
                        story, created = InstagramStory.objects.get_or_create(
                            story_id=story_data.get("story_id"),
                            account=self.account,
                            defaults={
                                "story_url": story_data.get("media_url", ""),
                                "media_type": story_data.get("media_type", ""),
                                "caption": story_data.get("caption", ""),
                                "story_timestamp": timezone.datetime.fromtimestamp(
                                    story_data.get(
                                        "timestamp", timezone.now().timestamp(),
                                    ),
                                    tz=timezone.utc,
                                ),
                                "expires_at": timezone.datetime.fromtimestamp(
                                    story_data.get(
                                        "expires_at", timezone.now().timestamp() + 86400,
                                    ),
                                    tz=timezone.utc,
                                ),
                            },
                        )

                        webhook_event.mark_as_processed(
                            {
                                "story_id": story.story_id,
                                "action": "story_insights_received",
                            },
                        )

                        logger.info(f"Processed story event: {story.story_id}")

        except Exception as e:
            logger.error(f"Error processing story event: {e!s}")
            webhook_event.mark_as_failed(str(e))


@method_decorator(csrf_exempt, name="dispatch")
class InstagramWebhookView(View):
    """Django view for handling Instagram webhook requests."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Handle webhook verification."""
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe":
            # Find account with matching verify token
            try:
                account = InstagramAccount.objects.get(verify_token=token)
                logger.info(f"Webhook verification successful for {account.username}")
                return HttpResponse(challenge, content_type="text/plain")
            except InstagramAccount.DoesNotExist:
                logger.error(f"Invalid verify token: {token}")
                return HttpResponse("Invalid verify token", status=403)

        return HttpResponse("Invalid request", status=400)

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle webhook events."""
        try:
            # Parse request body
            body = request.body
            signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")

            # Parse JSON data
            try:
                event_data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook request")
                return HttpResponse("Invalid JSON", status=400)

            # Determine which account this event is for
            account = self._get_account_for_event(event_data)
            if not account:
                logger.error("Could not determine account for webhook event")
                return HttpResponse("Account not found", status=404)

            # Verify signature
            handler = InstagramWebhookHandler(account)
            if not handler.verify_signature(body, signature):
                logger.error(f"Invalid webhook signature for {account.username}")
                return HttpResponse("Invalid signature", status=403)

            # Process the event
            handler.process_webhook_event(event_data)

            return HttpResponse("OK", status=200)

        except Exception as e:
            logger.error(f"Error handling webhook: {e!s}")
            return HttpResponse("Internal error", status=500)

    def _get_account_for_event(self, event_data: dict) -> InstagramAccount | None:
        """Determine which Instagram account this event belongs to."""
        try:
            # Extract account ID from event data
            for entry in event_data.get("entry", []):
                entry_id = entry.get("id")
                if entry_id:
                    # Try to find account by Instagram business account ID
                    try:
                        return InstagramAccount.objects.get(
                            instagram_business_account_id=entry_id,
                        )
                    except InstagramAccount.DoesNotExist:
                        continue

            return None

        except Exception as e:
            logger.error(f"Error determining account for event: {e!s}")
            return None


# Convenience function for webhook URL routing
def instagram_webhook_view(request):
    """Function-based view wrapper for InstagramWebhookView."""
    view = InstagramWebhookView()
    return view.dispatch(request)
