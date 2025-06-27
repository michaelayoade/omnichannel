import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from whatsapp_integration.models import (
    WhatsAppBusinessAccount,
    WhatsAppMessage,
    WhatsAppRateLimit,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)


class Command(BaseCommand):
    help = "Monitor WhatsApp integration health and statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-account-id",
            type=str,
            help="Specific business account to monitor",
        )

        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Time window in hours to analyze (default: 24)",
        )

        parser.add_argument(
            "--format",
            type=str,
            choices=["table", "json"],
            default="table",
            help="Output format",
        )

    def handle(self, *args, **options):
        self.options = options
        self.time_window = timezone.now() - timedelta(hours=options["hours"])

        if options["business_account_id"]:
            try:
                business_account = WhatsAppBusinessAccount.objects.get(
                    business_account_id=options["business_account_id"],
                )
                accounts = [business_account]
            except WhatsAppBusinessAccount.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Business account {options["business_account_id"]} not found',
                    ),
                )
                return
        else:
            accounts = WhatsAppBusinessAccount.objects.filter(is_active=True)

        if options["format"] == "json":
            self._output_json(accounts)
        else:
            self._output_table(accounts)

    def _output_table(self, accounts):
        """Output monitoring data in table format."""
        self.stdout.write(
            self.style.SUCCESS(
                f'\nWhatsApp Integration Monitor - Last {self.options["hours"]} hours',
            ),
        )
        self.stdout.write("=" * 80)

        for account in accounts:
            self._show_account_summary(account)
            self._show_message_stats(account)
            self._show_webhook_stats(account)
            self._show_rate_limit_stats(account)
            self._show_template_stats(account)
            self.stdout.write("-" * 80)

    def _output_json(self, accounts):
        """Output monitoring data in JSON format."""
        data = {
            "timestamp": timezone.now().isoformat(),
            "time_window_hours": self.options["hours"],
            "accounts": [],
        }

        for account in accounts:
            account_data = {
                "business_account_id": account.business_account_id,
                "name": account.name,
                "phone_number": account.display_phone_number,
                "is_active": account.is_active,
                "messages": self._get_message_stats(account),
                "webhooks": self._get_webhook_stats(account),
                "rate_limits": self._get_rate_limit_stats(account),
                "templates": self._get_template_stats(account),
            }
            data["accounts"].append(account_data)

        self.stdout.write(json.dumps(data, indent=2))

    def _show_account_summary(self, account):
        """Show account summary information."""
        self.stdout.write(f"\n📱 Account: {account.name}")
        self.stdout.write(f"   ID: {account.business_account_id}")
        self.stdout.write(f"   Phone: {account.display_phone_number}")
        self.stdout.write(
            f'   Status: {"🟢 Active" if account.is_active else "🔴 Inactive"}',
        )

    def _show_message_stats(self, account):
        """Show message statistics."""
        stats = self._get_message_stats(account)

        self.stdout.write(f'\n📨 Messages (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Inbound: {stats["inbound"]} | Outbound: {stats["outbound"]}',
        )
        self.stdout.write(
            f'   Sent: {stats["sent"]} | Delivered: {stats["delivered"]} | '
            f'Read: {stats["read"]}',
        )
        self.stdout.write(f'   Failed: {stats["failed"]}')

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed messages detected'),
            )

    def _show_webhook_stats(self, account):
        """Show webhook statistics."""
        stats = self._get_webhook_stats(account)

        self.stdout.write(f'\n🔗 Webhooks (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Processed: {stats["processed"]} | Failed: {stats["failed"]} | '
            f'Pending: {stats["pending"]}',
        )

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed webhooks'),
            )

    def _show_rate_limit_stats(self, account):
        """Show rate limiting statistics."""
        stats = self._get_rate_limit_stats(account)

        self.stdout.write("\n⏱️  Rate Limits:")
        self.stdout.write(f'   Current hour requests: {stats["current_hour_requests"]}')
        self.stdout.write(f'   Rate limit hits: {stats["rate_limit_hits"]}')

        if stats["rate_limit_hits"] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'   ⚠️  Rate limit exceeded {stats["rate_limit_hits"]} times',
                ),
            )

    def _show_template_stats(self, account):
        """Show template statistics."""
        stats = self._get_template_stats(account)

        self.stdout.write("\n📋 Templates:")
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Approved: {stats["approved"]} | Pending: {stats["pending"]} | '
            f'Rejected: {stats["rejected"]}',
        )

    def _get_message_stats(self, account):
        """Get message statistics for an account."""
        messages = WhatsAppMessage.objects.filter(
            business_account=account, created_at__gte=self.time_window,
        )

        return {
            "total": messages.count(),
            "inbound": messages.filter(direction="inbound").count(),
            "outbound": messages.filter(direction="outbound").count(),
            "sent": messages.filter(status="sent").count(),
            "delivered": messages.filter(status="delivered").count(),
            "read": messages.filter(status="read").count(),
            "failed": messages.filter(status="failed").count(),
            "pending": messages.filter(status="pending").count(),
        }

    def _get_webhook_stats(self, account):
        """Get webhook statistics for an account."""
        webhooks = WhatsAppWebhookEvent.objects.filter(
            business_account=account, created_at__gte=self.time_window,
        )

        return {
            "total": webhooks.count(),
            "processed": webhooks.filter(processing_status="processed").count(),
            "failed": webhooks.filter(processing_status="failed").count(),
            "pending": webhooks.filter(processing_status="pending").count(),
            "processing": webhooks.filter(processing_status="processing").count(),
        }

    def _get_rate_limit_stats(self, account):
        """Get rate limiting statistics for an account."""
        current_hour = timezone.now().replace(minute=0, second=0, microsecond=0)

        current_hour_limits = WhatsAppRateLimit.objects.filter(
            business_account=account, window_start=current_hour,
        )

        rate_limit_hits = WhatsAppRateLimit.objects.filter(
            business_account=account,
            window_start__gte=self.time_window,
            is_blocked=True,
        ).count()

        current_hour_requests = sum(
            limit.request_count for limit in current_hour_limits
        )

        return {
            "current_hour_requests": current_hour_requests,
            "rate_limit_hits": rate_limit_hits,
        }

    def _get_template_stats(self, account):
        """Get template statistics for an account."""
        templates = WhatsAppTemplate.objects.filter(business_account=account)

        return {
            "total": templates.count(),
            "approved": templates.filter(status="approved").count(),
            "pending": templates.filter(status="pending").count(),
            "rejected": templates.filter(status="rejected").count(),
            "disabled": templates.filter(status="disabled").count(),
        }
