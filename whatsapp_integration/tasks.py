import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import (
    WhatsAppBusinessAccount,
    WhatsAppMediaFile,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)
from .services.whatsapp_api import WhatsAppBusinessAPI, WhatsAppMessageService
from .webhooks.handlers import WhatsAppWebhookProcessor

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_whatsapp_webhook(self, webhook_event_id: int):
    """Process WhatsApp webhook event asynchronously."""
    try:
        webhook_event = WhatsAppWebhookEvent.objects.get(id=webhook_event_id)
        webhook_event.processing_status = "processing"
        webhook_event.save()

        processor = WhatsAppWebhookProcessor(webhook_event.business_account)
        processor.process_webhook(webhook_event.payload)

        webhook_event.processing_status = "processed"
        webhook_event.processed_at = timezone.now()
        webhook_event.save()

        logger.info(f"Successfully processed webhook event {webhook_event_id}")

    except WhatsAppWebhookEvent.DoesNotExist:
        logger.error(f"Webhook event {webhook_event_id} not found")
        return

    except Exception as e:
        webhook_event.processing_status = "failed"
        webhook_event.error_message = str(e)
        webhook_event.retry_count += 1
        webhook_event.save()

        logger.error(f"Error processing webhook event {webhook_event_id}: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries), exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_whatsapp_message(
    self,
    business_account_id: str,
    to: str,
    message_type: str,
    content: str = None,
    media_id: str = None,
    media_url: str = None,
    template_name: str = None,
    template_components: list = None,
    interactive_data: dict = None,
):
    """Send WhatsApp message asynchronously."""
    try:
        business_account = WhatsAppBusinessAccount.objects.get(
            business_account_id=business_account_id, is_active=True
        )

        message_service = WhatsAppMessageService(business_account)
        message = message_service.send_message(
            to=to,
            message_type=message_type,
            content=content,
            media_id=media_id,
            media_url=media_url,
            template_name=template_name,
            template_components=template_components,
            interactive_data=interactive_data,
        )

        logger.info(f"Message sent successfully: {message.wa_message_id}")
        return message.wa_message_id

    except WhatsAppBusinessAccount.DoesNotExist:
        logger.error(f"Business account {business_account_id} not found")
        return None

    except Exception as e:
        logger.error(f"Error sending message: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (2**self.request.retries), exc=e)

        return None


@shared_task
def download_whatsapp_media(media_file_id: int):
    """Download WhatsApp media file asynchronously."""
    try:
        media_file = WhatsAppMediaFile.objects.get(id=media_file_id)

        if media_file.is_downloaded:
            logger.info(f"Media file {media_file_id} already downloaded")
            return

        api = WhatsAppBusinessAPI(media_file.business_account)
        content, filename, mime_type = api.download_media(media_file.media_id)

        # Save file content
        from django.core.files.base import ContentFile

        file_content = ContentFile(content, name=filename)
        media_file.file_path.save(filename, file_content)

        # Update media file record
        media_file.filename = filename
        media_file.mime_type = mime_type
        media_file.file_size = len(content)
        media_file.is_downloaded = True
        media_file.save()

        logger.info(f"Successfully downloaded media file: {filename}")

    except WhatsAppMediaFile.DoesNotExist:
        logger.error(f"Media file {media_file_id} not found")

    except Exception as e:
        logger.error(f"Error downloading media file {media_file_id}: {e}")


@shared_task
def sync_whatsapp_templates(business_account_id: str):
    """Sync WhatsApp message templates from API."""
    try:
        business_account = WhatsAppBusinessAccount.objects.get(
            business_account_id=business_account_id, is_active=True
        )

        api = WhatsAppBusinessAPI(business_account)
        templates_data = api.get_templates()

        synced_count = 0
        for template_data in templates_data:
            template, created = WhatsAppTemplate.objects.update_or_create(
                business_account=business_account,
                name=template_data["name"],
                language=template_data["language"],
                defaults={
                    "status": template_data["status"],
                    "category": template_data["category"],
                    "components": template_data.get("components", []),
                    "quality_score": template_data.get("quality_score", {}).get(
                        "score", ""
                    ),
                },
            )

            if created:
                synced_count += 1

        logger.info(
            f"Synced {synced_count} WhatsApp templates for {business_account.name}"
        )

    except WhatsAppBusinessAccount.DoesNotExist:
        logger.error(f"Business account {business_account_id} not found")

    except Exception as e:
        logger.error(f"Error syncing templates for {business_account_id}: {e}")


@shared_task
def cleanup_old_webhook_events():
    """Clean up old webhook events to prevent database bloat."""
    try:
        # Delete processed events older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = WhatsAppWebhookEvent.objects.filter(
            processing_status="processed", processed_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old webhook events")

        # Delete failed events older than 7 days
        failed_cutoff_date = timezone.now() - timedelta(days=7)
        failed_deleted_count = WhatsAppWebhookEvent.objects.filter(
            processing_status="failed", created_at__lt=failed_cutoff_date
        ).delete()[0]

        logger.info(f"Cleaned up {failed_deleted_count} old failed webhook events")

    except Exception as e:
        logger.error(f"Error cleaning up webhook events: {e}")


@shared_task
def cleanup_old_media_files():
    """Clean up old media files to save storage space."""
    try:
        # Delete media files older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)

        old_media_files = WhatsAppMediaFile.objects.filter(
            created_at__lt=cutoff_date, is_downloaded=True
        )

        deleted_count = 0
        for media_file in old_media_files:
            try:
                # Delete physical file
                if media_file.file_path:
                    media_file.file_path.delete(save=False)

                # Delete database record
                media_file.delete()
                deleted_count += 1

            except Exception as e:
                logger.error(f"Error deleting media file {media_file.id}: {e}")

        logger.info(f"Cleaned up {deleted_count} old media files")

    except Exception as e:
        logger.error(f"Error cleaning up media files: {e}")


@shared_task
def retry_failed_messages():
    """Retry sending failed WhatsApp messages."""
    try:
        # Get failed messages from the last hour
        cutoff_time = timezone.now() - timedelta(hours=1)
        failed_messages = WhatsAppMessage.objects.filter(
            status="failed", direction="outbound", failed_at__gt=cutoff_time
        ).select_related("business_account", "contact")

        retry_count = 0
        for message in failed_messages:
            try:
                # Attempt to resend the message
                message_service = WhatsAppMessageService(message.business_account)

                if message.message_type == "text":
                    response = message_service.api.send_text_message(
                        message.contact.wa_id, message.content
                    )
                elif message.message_type in ["image", "audio", "video", "document"]:
                    response = message_service.api.send_media_message(
                        message.contact.wa_id,
                        message.message_type,
                        message.media_id,
                        message.media_url,
                        message.content,
                    )
                else:
                    logger.warning(f"Cannot retry message type {message.message_type}")
                    continue

                # Update message status
                message.wa_message_id = response["messages"][0]["id"]
                message.status = "sent"
                message.sent_at = timezone.now()
                message.error_code = ""
                message.error_message = ""
                message.save()

                retry_count += 1
                logger.info(f"Successfully retried message {message.id}")

            except Exception as e:
                logger.error(f"Error retrying message {message.id}: {e}")

        logger.info(f"Retried {retry_count} failed messages")

    except Exception as e:
        logger.error(f"Error retrying failed messages: {e}")


@shared_task
def update_contact_profiles():
    """Update WhatsApp contact profiles with latest information."""
    try:
        from .models import WhatsAppContact

        # Get contacts that haven't been updated in the last 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        contacts_to_update = WhatsAppContact.objects.filter(
            updated_at__lt=cutoff_time, is_opted_in=True
        ).select_related("business_account")

        updated_count = 0
        for contact in contacts_to_update[:100]:  # Limit to prevent rate limiting
            try:
                # This would require additional WhatsApp Business API calls
                # to get contact profile information
                # Implementation depends on available API endpoints

                contact.updated_at = timezone.now()
                contact.save()
                updated_count += 1

            except Exception as e:
                logger.error(f"Error updating contact {contact.id}: {e}")

        logger.info(f"Updated {updated_count} contact profiles")

    except Exception as e:
        logger.error(f"Error updating contact profiles: {e}")


# Periodic task setup (add to Django settings)
CELERY_BEAT_SCHEDULE = {
    "sync-whatsapp-templates": {
        "task": "whatsapp_integration.tasks.sync_whatsapp_templates",
        "schedule": timedelta(hours=6),  # Sync templates every 6 hours
    },
    "cleanup-old-webhook-events": {
        "task": "whatsapp_integration.tasks.cleanup_old_webhook_events",
        "schedule": timedelta(days=1),  # Daily cleanup
    },
    "cleanup-old-media-files": {
        "task": "whatsapp_integration.tasks.cleanup_old_media_files",
        "schedule": timedelta(days=7),  # Weekly cleanup
    },
    "retry-failed-messages": {
        "task": "whatsapp_integration.tasks.retry_failed_messages",
        "schedule": timedelta(minutes=30),  # Retry every 30 minutes
    },
    "update-contact-profiles": {
        "task": "whatsapp_integration.tasks.update_contact_profiles",
        "schedule": timedelta(hours=12),  # Update profiles twice daily
    },
}
