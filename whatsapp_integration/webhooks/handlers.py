import hashlib
import hmac
import json
import logging
from typing import Any, ClassVar

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..models import WhatsAppBusinessAccount, WhatsAppWebhookEvent
from ..services.whatsapp_api import WhatsAppMessageService

logger = logging.getLogger(__name__)


class WhatsAppWebhookSecurity:
    """Handle WhatsApp webhook security verification."""

    @staticmethod
    def verify_webhook_signature(
        payload: bytes, signature: str, verify_token: str,
    ) -> bool:
        """Verify webhook signature using HMAC-SHA256.

        Args:
        ----
            payload: Raw request body
            signature: X-Hub-Signature-256 header value
            verify_token: Webhook verify token

        Returns:
        -------
            True if signature is valid, False otherwise

        """
        try:
            # Remove 'sha256=' prefix if present
            if signature.startswith("sha256="):
                signature = signature[7:]

            # Calculate expected signature
            expected_signature = hmac.new(
                verify_token.encode("utf-8"), payload, hashlib.sha256,
            ).hexdigest()

            # Compare signatures using constant-time comparison
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    @staticmethod
    def verify_webhook_challenge(
        verify_token: str, challenge: str, token: str,
    ) -> str | None:
        """Verify webhook challenge for initial setup.

        Args:
        ----
            verify_token: Expected verify token
            challenge: Challenge string from webhook
            token: Token from webhook request

        Returns:
        -------
            Challenge string if verification succeeds, None otherwise

        """
        if token == verify_token:
            return challenge
        return None


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(View):
    """Handle WhatsApp webhook requests."""

    def get(self, request, business_account_id: str):
        """Handle webhook verification (GET request)."""
        try:
            # Get business account
            try:
                business_account = WhatsAppBusinessAccount.objects.get(
                    business_account_id=business_account_id, is_active=True,
                )
            except WhatsAppBusinessAccount.DoesNotExist:
                logger.error(f"Business account not found: {business_account_id}")
                return HttpResponseBadRequest("Invalid business account")

            # Extract verification parameters
            mode = request.GET.get("hub.mode")
            token = request.GET.get("hub.verify_token")
            challenge = request.GET.get("hub.challenge")

            if mode != "subscribe":
                return HttpResponseBadRequest("Invalid mode")

            # Verify token
            verified_challenge = WhatsAppWebhookSecurity.verify_webhook_challenge(
                business_account.webhook_verify_token, challenge, token,
            )

            if verified_challenge:
                logger.info(
                    f"Webhook verification successful for {business_account_id}",
                )
                return HttpResponse(verified_challenge, content_type="text/plain")
            else:
                logger.error(f"Webhook verification failed for {business_account_id}")
                return HttpResponseBadRequest("Verification failed")

        except Exception as e:
            logger.error(f"Error in webhook verification: {e}")
            return HttpResponseBadRequest("Verification error")

    def post(self, request, business_account_id: str):
        """Handle webhook notifications (POST request)."""
        try:
            # Get business account
            try:
                business_account = WhatsAppBusinessAccount.objects.get(
                    business_account_id=business_account_id, is_active=True,
                )
            except WhatsAppBusinessAccount.DoesNotExist:
                logger.error(f"Business account not found: {business_account_id}")
                return HttpResponseBadRequest("Invalid business account")

            # Verify signature
            signature = request.headers.get("X-Hub-Signature-256", "")
            if not WhatsAppWebhookSecurity.verify_webhook_signature(
                request.body, signature, business_account.webhook_verify_token,
            ):
                logger.error(f"Invalid webhook signature for {business_account_id}")
                return HttpResponseBadRequest("Invalid signature")

            # Parse webhook data
            try:
                webhook_data = json.loads(request.body)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in webhook: {e}")
                return HttpResponseBadRequest("Invalid JSON")

            # Process webhook asynchronously
            self._process_webhook_async(business_account, webhook_data)

            return HttpResponse("OK")

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return HttpResponseBadRequest("Processing error")

    def _process_webhook_async(
        self, business_account: WhatsAppBusinessAccount, webhook_data: dict,
    ):
        """Process webhook data asynchronously."""
        try:
            # Create webhook event record
            webhook_event = WhatsAppWebhookEvent.objects.create(
                business_account=business_account,
                event_type=self._determine_event_type(webhook_data),
                payload=webhook_data,
                processing_status="pending",
            )

            # Process webhook using Celery task (if available) or directly
            if hasattr(settings, "CELERY_BROKER_URL"):
                from ..tasks import process_whatsapp_webhook

                process_whatsapp_webhook.delay(webhook_event.id)
            else:
                self._process_webhook_sync(webhook_event)

        except Exception as e:
            logger.error(f"Error creating webhook event: {e}")

    def _process_webhook_sync(self, webhook_event: WhatsAppWebhookEvent):
        """Process webhook synchronously."""
        try:
            webhook_event.processing_status = "processing"
            webhook_event.save()

            processor = WhatsAppWebhookProcessor(webhook_event.business_account)
            processor.process_webhook(webhook_event.payload)

            webhook_event.processing_status = "processed"
            webhook_event.processed_at = timezone.now()
            webhook_event.save()

        except Exception as e:
            webhook_event.processing_status = "failed"
            webhook_event.error_message = str(e)
            webhook_event.save()
            logger.error(f"Error processing webhook {webhook_event.id}: {e}")

    def _determine_event_type(self, webhook_data: dict[str, Any]) -> str:
        """Determine the type of webhook event."""
        entry = webhook_data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        if "messages" in value:
            return "messages"
        if "statuses" in value:
            return "message_status"
        if "account_alerts" in value:
            return "account_alerts"
        return "unknown"


class WhatsAppWebhookProcessor:
    """Process different types of WhatsApp webhook events."""

    # Event type constants
    EVENT_TYPE_MESSAGES: ClassVar[str] = "messages"
    EVENT_TYPE_STATUSES: ClassVar[str] = "statuses"
    EVENT_TYPE_ACCOUNT_ALERTS: ClassVar[str] = "account_alerts"

    def __init__(self, business_account: WhatsAppBusinessAccount):
        self.business_account = business_account
        self.message_service = WhatsAppMessageService(business_account)

    def process_webhook(self, webhook_data: dict[str, Any]) -> None:
        """Process webhook based on its type.
        
        Args:
        ----
            webhook_data: The webhook payload received from WhatsApp

        """
        entry = webhook_data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        if "messages" in value:
            self._process_message_event(webhook_data)
            return

        if "statuses" in value:
            self._process_status_event(webhook_data)
            return

        if "account_alerts" in value:
            self._process_account_alert_event(webhook_data)
            return

        logger.warning(f"Unknown webhook event type: {webhook_data}")

    def _process_message_event(self, webhook_data: dict):
        """Process incoming message event."""
        try:
            message = self.message_service.process_incoming_message(webhook_data)
            if message:
                logger.info(f"Processed incoming message: {message.wa_message_id}")

                # Auto-mark as read if configured
                if getattr(settings, "WHATSAPP_AUTO_MARK_READ", False):
                    try:
                        self.message_service.api.mark_message_as_read(
                            message.wa_message_id,
                        )
                        message.read_at = timezone.now()
                        message.save()
                    except Exception as e:
                        logger.error(f"Error marking message as read: {e}")

                # Trigger conversation creation or update
                self._handle_conversation_update(message)

        except Exception as e:
            logger.error(f"Error processing message event: {e}")

    def _process_status_event(self, webhook_data: dict):
        """Process message status update event."""
        try:
            self.message_service.update_message_status(webhook_data)
            logger.info("Processed message status update")
        except Exception as e:
            logger.error(f"Error processing status event: {e}")

    def _process_account_alert_event(self, webhook_data: dict):
        """Process account alert event."""
        try:
            entry = webhook_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            # Log account alerts for monitoring
            alerts = value.get("account_alerts", [])
            for alert in alerts:
                logger.warning(f"WhatsApp account alert: {alert}")

                # TODO: Implement alert notifications (email, Slack, etc.)

        except Exception as e:
            logger.error(f"Error processing account alert: {e}")

    def _handle_conversation_update(self, message):
        """Handle conversation creation or update based on incoming message."""
        try:
            from communication_channels.models import CommunicationChannel
            from conversations.models import Conversation
            from conversations.models import Message as ConversationMessage

            # Get or create WhatsApp channel
            whatsapp_channel, created = CommunicationChannel.objects.get_or_create(
                channel_type="whatsapp",
                name=f"WhatsApp - {self.business_account.display_phone_number}",
                defaults={"status": "active", "is_inbound": True, "is_outbound": True},
            )

            # Get customer associated with WhatsApp contact
            customer = message.contact.customer
            if not customer:
                # Create a customer if one doesn't exist
                from customers.models import Customer

                customer = Customer.objects.create(
                    customer_id=f"wa_{message.contact.wa_id}",
                    first_name=(
                        message.contact.profile_name.split(" ")[0]
                        if message.contact.profile_name
                        else "Unknown"
                    ),
                    last_name=(
                        " ".join(message.contact.profile_name.split(" ")[1:])
                        if len(message.contact.profile_name.split(" ")) > 1
                        else ""
                    ),
                    email="",
                    phone=message.contact.phone_number,
                )
                message.contact.customer = customer
                message.contact.save()

            # Get or create conversation
            conversation, created = Conversation.objects.get_or_create(
                customer=customer,
                channel=whatsapp_channel,
                status__in=["open", "pending"],
                defaults={
                    "conversation_id": (
                        f"wa_{message.contact.wa_id}_"
                        f"{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                    ),
                    "status": "open",
                    "priority": "normal",
                },
            )

            # Create conversation message
            ConversationMessage.objects.create(
                conversation=conversation,
                message_id=f"wa_{message.wa_message_id}",
                external_message_id=message.wa_message_id,
                sender_type="customer",
                sender_name=message.contact.profile_name
                or message.contact.phone_number,
                message_type=message.message_type,
                content=message.content,
                raw_content={
                    "whatsapp_message_id": message.wa_message_id,
                    "media_id": message.media_id,
                    "media_url": message.media_url,
                    "media_filename": message.media_filename,
                },
                timestamp=message.timestamp,
            )

            # Update conversation timestamp
            conversation.updated_at = timezone.now()
            conversation.save()

            logger.info(
                f"Updated conversation {conversation.conversation_id} with "
                f"message {message.wa_message_id}",
            )

        except Exception as e:
            logger.error(f"Error handling conversation update: {e}")


# URL patterns helper
def get_webhook_urls():
    """Get URL patterns for WhatsApp webhooks."""
    from django.urls import path

    return [
        path(
            "whatsapp/webhook/<str:business_account_id>/",
            WhatsAppWebhookView.as_view(),
            name="whatsapp_webhook",
        ),
    ]
