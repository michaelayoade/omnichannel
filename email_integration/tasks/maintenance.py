import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import (
    EmailAccount,
    EmailContact,
    EmailMessage,
    EmailPollLog,
    EmailTemplate,
)

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_emails():
    """Clean up old email messages and attachments."""
    try:
        # Delete messages older than specified days (configurable)
        retention_days = getattr(settings, "EMAIL_RETENTION_DAYS", 365)
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Delete old messages
        old_messages = EmailMessage.objects.filter(received_at__lt=cutoff_date)

        deleted_count = 0
        for message in old_messages:
            # Delete associated attachments first
            for attachment in message.attachments.all():
                if attachment.file_path:
                    attachment.file_path.delete(save=False)
                attachment.delete()

            message.delete()
            deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old email messages")

        # Clean up old poll logs
        old_poll_logs = EmailPollLog.objects.filter(started_at__lt=cutoff_date)
        poll_log_count = old_poll_logs.count()
        old_poll_logs.delete()

        logger.info(f"Cleaned up {poll_log_count} old poll logs")

        return {"deleted_messages": deleted_count, "deleted_poll_logs": poll_log_count}
    except Exception as e:
        logger.error(f"Error during email cleanup: {e}")
        return None


@shared_task
def update_email_statistics():
    """Update email statistics for accounts and contacts."""
    try:
        # Update account statistics
        for account in EmailAccount.objects.filter(status="active"):
            total_sent = account.messages.filter(direction="outbound").count()
            total_received = account.messages.filter(direction="inbound").count()

            account.total_emails_sent = total_sent
            account.total_emails_received = total_received
            account.save(update_fields=["total_emails_sent", "total_emails_received"])

        # Update contact statistics
        for contact in EmailContact.objects.all():
            received_count = EmailMessage.objects.filter(
                account=contact.account,
                from_email=contact.email_address,
                direction="inbound",
            ).count()

            sent_count = (
                EmailMessage.objects.filter(
                    account=contact.account, direction="outbound"
                )
                .filter(to_emails__contains=contact.email_address)
                .count()
            )

            last_email = (
                EmailMessage.objects.filter(
                    account=contact.account, from_email=contact.email_address
                )
                .order_by("-received_at")
                .first()
            )

            contact.total_emails_received = received_count
            contact.total_emails_sent = sent_count
            if last_email:
                contact.last_email_at = last_email.received_at
            contact.save()

        logger.info("Updated email statistics")

    except Exception as e:
        logger.error(f"Error updating email statistics: {e}")


@shared_task
def process_bounced_emails():
    """Process bounced email notifications."""
    try:
        # This would typically process bounce notifications from your email provider
        # For now, we'll just identify failed messages that might be bounces

        failed_messages = EmailMessage.objects.filter(
            status="failed", direction="outbound", error_code__isnull=False
        )

        bounce_count = 0
        for message in failed_messages:
            # Check if error indicates a bounce
            error_msg = message.error_message.lower()
            bounce_indicators = [
                "mailbox unavailable",
                "user unknown",
                "address not found",
                "delivery failed",
                "bounce",
            ]

            if any(indicator in error_msg for indicator in bounce_indicators):
                message.status = "bounced"
                message.bounced_at = timezone.now()
                message.save()
                bounce_count += 1

        logger.info(f"Processed {bounce_count} bounced emails")
        return bounce_count

    except Exception as e:
        logger.error(f"Error processing bounced emails: {e}")
        return 0


@shared_task
def sync_email_templates():
    """Sync email templates across accounts."""
    try:
        # Update global templates for all accounts
        global_templates = EmailTemplate.objects.filter(is_global=True, is_active=True)

        sync_count = 0
        for account in EmailAccount.objects.filter(status="active"):
            for template in global_templates:
                # Check if account-specific version exists
                account_template = EmailTemplate.objects.filter(
                    account=account,
                    name=template.name,
                    template_type=template.template_type,
                ).first()

                if not account_template:
                    # Create account-specific copy
                    EmailTemplate.objects.create(
                        account=account,
                        name=template.name,
                        template_type=template.template_type,
                        subject=template.subject,
                        plain_content=template.plain_content,
                        html_content=template.html_content,
                        variables=template.variables,
                        is_active=template.is_active,
                        is_global=False,
                    )
                    sync_count += 1

        logger.info(f"Synced {sync_count} email templates")
        return sync_count

    except Exception as e:
        logger.error(f"Error syncing email templates: {e}")
        return 0
