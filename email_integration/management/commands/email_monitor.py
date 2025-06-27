import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from email_integration.models import (
    EmailAccount,
    EmailMessage,
    EmailPollLog,
    EmailThread,
)


class Command(BaseCommand):
    help = "Monitor email integration health and statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id", type=int, help="Specific email account to monitor"
        )

        parser.add_argument(
            "--email-address", type=str, help="Email address of account to monitor"
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

        parser.add_argument(
            "--show-errors", action="store_true", help="Show detailed error information"
        )

    def handle(self, *args, **options):
        self.options = options
        self.time_window = timezone.now() - timedelta(hours=options["hours"])

        if options["account_id"] or options["email_address"]:
            try:
                if options["account_id"]:
                    account = EmailAccount.objects.get(id=options["account_id"])
                else:
                    account = EmailAccount.objects.get(
                        email_address=options["email_address"]
                    )
                accounts = [account]
            except EmailAccount.DoesNotExist:
                self.stdout.write(self.style.ERROR("Email account not found"))
                return
        else:
            accounts = EmailAccount.objects.all()

        if options["format"] == "json":
            self._output_json(accounts)
        else:
            self._output_table(accounts)

    def _output_table(self, accounts):
        """Output monitoring data in table format."""
        self.stdout.write(
            self.style.SUCCESS(
                f'\nEmail Integration Monitor - Last {self.options["hours"]} hours'
            )
        )
        self.stdout.write("=" * 80)

        for account in accounts:
            self._show_account_summary(account)
            self._show_message_stats(account)
            self._show_polling_stats(account)
            self._show_contact_stats(account)
            self._show_thread_stats(account)

            if self.options["show_errors"]:
                self._show_error_details(account)

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
                "id": account.id,
                "name": account.name,
                "email_address": account.email_address,
                "status": account.status,
                "account_type": account.account_type,
                "is_healthy": account.is_healthy,
                "messages": self._get_message_stats(account),
                "polling": self._get_polling_stats(account),
                "contacts": self._get_contact_stats(account),
                "threads": self._get_thread_stats(account),
                "errors": (
                    self._get_error_info(account)
                    if self.options["show_errors"]
                    else None
                ),
            }
            data["accounts"].append(account_data)

        self.stdout.write(json.dumps(data, indent=2))

    def _show_account_summary(self, account):
        """Show account summary information."""
        status_icon = "🟢" if account.is_healthy else "🔴"

        self.stdout.write(f"\n📧 Account: {account.name}")
        self.stdout.write(f"   Email: {account.email_address}")
        self.stdout.write(f"   Type: {account.get_account_type_display()}")
        self.stdout.write(f"   Status: {status_icon} {account.get_status_display()}")
        self.stdout.write(f"   Protocol: {account.get_incoming_protocol_display()}")

        if account.last_poll_at:
            time_since_poll = timezone.now() - account.last_poll_at
            self.stdout.write(
                f"   Last Poll: {self._format_duration(time_since_poll)} ago"
            )
        else:
            self.stdout.write("   Last Poll: Never")

        if account.last_error_message:
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠️  Last Error: {account.last_error_message[:100]}..."
                )
            )

    def _show_message_stats(self, account):
        """Show message statistics."""
        stats = self._get_message_stats(account)

        self.stdout.write(f'\n📨 Messages (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Inbound: {stats["inbound"]} | Outbound: {stats["outbound"]}'
        )
        self.stdout.write(f'   Sent: {stats["sent"]} | Failed: {stats["failed"]}')
        self.stdout.write(f'   With Attachments: {stats["with_attachments"]}')

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed messages')
            )

    def _show_polling_stats(self, account):
        """Show polling statistics."""
        stats = self._get_polling_stats(account)

        self.stdout.write(f'\n🔄 Polling (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total Polls: {stats["total_polls"]}')
        self.stdout.write(
            f'   Successful: {stats["successful"]} | Failed: {stats["failed"]}'
        )
        self.stdout.write(f'   Messages Found: {stats["messages_found"]}')
        self.stdout.write(f'   Processing Rate: {stats["processing_rate"]:.1f}%')

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed polls')
            )

    def _show_contact_stats(self, account):
        """Show contact statistics."""
        stats = self._get_contact_stats(account)

        self.stdout.write("\n👥 Contacts:")
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(f'   New (last {self.options["hours"]}h): {stats["new"]}')
        self.stdout.write(f'   Active: {stats["active"]}')

    def _show_thread_stats(self, account):
        """Show thread statistics."""
        stats = self._get_thread_stats(account)

        self.stdout.write("\n🧵 Threads:")
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(f'   Active: {stats["active"]}')
        self.stdout.write(f'   New (last {self.options["hours"]}h): {stats["new"]}')

    def _show_error_details(self, account):
        """Show detailed error information."""
        errors = self._get_error_info(account)

        if errors["recent_errors"]:
            self.stdout.write("\n❌ Recent Errors:")
            for error in errors["recent_errors"][:5]:  # Show last 5 errors
                self.stdout.write(
                    f'   • {error["timestamp"]}: {error["message"][:100]}...'
                )

    def _get_message_stats(self, account):
        """Get message statistics for an account."""
        messages = EmailMessage.objects.filter(
            account=account, received_at__gte=self.time_window
        )

        total = messages.count()
        inbound = messages.filter(direction="inbound").count()
        outbound = messages.filter(direction="outbound").count()
        sent = messages.filter(status="sent").count()
        failed = messages.filter(status="failed").count()
        with_attachments = messages.filter(attachments__isnull=False).distinct().count()

        return {
            "total": total,
            "inbound": inbound,
            "outbound": outbound,
            "sent": sent,
            "failed": failed,
            "with_attachments": with_attachments,
        }

    def _get_polling_stats(self, account):
        """Get polling statistics for an account."""
        polls = EmailPollLog.objects.filter(
            account=account, started_at__gte=self.time_window
        )

        total_polls = polls.count()
        successful = polls.filter(status="success").count()
        failed = polls.filter(status="error").count()
        messages_found = (
            polls.aggregate(total=models.Sum("messages_found"))["total"] or 0
        )
        messages_processed = (
            polls.aggregate(total=models.Sum("messages_processed"))["total"] or 0
        )

        processing_rate = 0
        if messages_found > 0:
            processing_rate = (messages_processed / messages_found) * 100

        return {
            "total_polls": total_polls,
            "successful": successful,
            "failed": failed,
            "messages_found": messages_found,
            "messages_processed": messages_processed,
            "processing_rate": processing_rate,
        }

    def _get_contact_stats(self, account):
        """Get contact statistics for an account."""

        all_contacts = EmailContact.objects.filter(account=account)
        new_contacts = all_contacts.filter(created_at__gte=self.time_window)
        active_contacts = all_contacts.filter(last_email_at__gte=self.time_window)

        return {
            "total": all_contacts.count(),
            "new": new_contacts.count(),
            "active": active_contacts.count(),
        }

    def _get_thread_stats(self, account):
        """Get thread statistics for an account."""
        all_threads = EmailThread.objects.filter(account=account)
        active_threads = all_threads.filter(status="open")
        new_threads = all_threads.filter(created_at__gte=self.time_window)

        return {
            "total": all_threads.count(),
            "active": active_threads.count(),
            "new": new_threads.count(),
        }

    def _get_error_info(self, account):
        """Get error information for an account."""
        recent_polls = EmailPollLog.objects.filter(
            account=account, status="error", started_at__gte=self.time_window
        ).order_by("-started_at")

        recent_messages = EmailMessage.objects.filter(
            account=account, status="failed", failed_at__gte=self.time_window
        ).order_by("-failed_at")

        errors = []

        # Add polling errors
        for poll in recent_polls:
            errors.append(
                {
                    "type": "polling",
                    "timestamp": poll.started_at.isoformat(),
                    "message": poll.error_message,
                }
            )

        # Add message errors
        for message in recent_messages:
            errors.append(
                {
                    "type": "message",
                    "timestamp": message.failed_at.isoformat(),
                    "message": message.error_message,
                }
            )

        # Sort by timestamp
        errors.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "recent_errors": errors,
            "polling_errors": recent_polls.count(),
            "message_errors": recent_messages.count(),
        }

    def _format_duration(self, duration):
        """Format timedelta as human-readable string."""
        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h"
        else:
            days = total_seconds // 86400
            return f"{days}d"
