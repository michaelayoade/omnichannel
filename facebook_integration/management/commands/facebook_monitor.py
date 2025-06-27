import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from facebook_integration.models import (
    FacebookConversationFlow,
    FacebookMessage,
    FacebookPage,
    FacebookUser,
    FacebookWebhookEvent,
)


class Command(BaseCommand):
    help = "Monitor Facebook Messenger integration health and statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id", type=str, help="Specific Facebook page to monitor"
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

        parser.add_argument(
            "--show-flows",
            action="store_true",
            help="Show conversation flow statistics",
        )

        parser.add_argument(
            "--show-users", action="store_true", help="Show user engagement statistics"
        )

    def handle(self, *args, **options):
        self.options = options
        self.time_window = timezone.now() - timedelta(hours=options["hours"])

        if options["page_id"]:
            try:
                page = FacebookPage.objects.get(page_id=options["page_id"])
                pages = [page]
            except FacebookPage.DoesNotExist:
                self.stdout.write(self.style.ERROR("Facebook page not found"))
                return
        else:
            pages = FacebookPage.objects.all()

        if options["format"] == "json":
            self._output_json(pages)
        else:
            self._output_table(pages)

    def _output_table(self, pages):
        """Output monitoring data in table format."""

        self.stdout.write(
            self.style.SUCCESS(
                f'\\nFacebook Messenger Monitor - Last {self.options["hours"]} hours'
            )
        )
        self.stdout.write("=" * 80)

        for page in pages:
            self._show_page_summary(page)
            self._show_message_stats(page)
            self._show_webhook_stats(page)

            if self.options["show_users"]:
                self._show_user_stats(page)

            if self.options["show_flows"]:
                self._show_flow_stats(page)

            if self.options["show_errors"]:
                self._show_error_details(page)

            self.stdout.write("-" * 80)

    def _output_json(self, pages):
        """Output monitoring data in JSON format."""

        data = {
            "timestamp": timezone.now().isoformat(),
            "time_window_hours": self.options["hours"],
            "pages": [],
        }

        for page in pages:
            page_data = {
                "page_id": page.page_id,
                "page_name": page.page_name,
                "status": page.status,
                "is_healthy": page.is_healthy,
                "webhook_subscribed": page.webhook_subscribed,
                "messages": self._get_message_stats(page),
                "webhooks": self._get_webhook_stats(page),
                "users": self._get_user_stats(page),
                "flows": (
                    self._get_flow_stats(page) if self.options["show_flows"] else None
                ),
                "errors": (
                    self._get_error_info(page) if self.options["show_errors"] else None
                ),
            }
            data["pages"].append(page_data)

        self.stdout.write(json.dumps(data, indent=2))

    def _show_page_summary(self, page):
        """Show page summary information."""

        status_icon = "🟢" if page.is_healthy else "🔴"
        webhook_icon = "✓" if page.webhook_subscribed else "✗"

        self.stdout.write(f"\\n📘 Page: {page.page_name}")
        self.stdout.write(f"   ID: {page.page_id}")
        self.stdout.write(f"   Status: {status_icon} {page.get_status_display()}")
        self.stdout.write(
            f'   Webhook: {webhook_icon} {"Subscribed" if page.webhook_subscribed else "Not Subscribed"}'
        )

        if page.last_health_check:
            time_since_check = timezone.now() - page.last_health_check
            self.stdout.write(
                f"   Last Health Check: {self._format_duration(time_since_check)} ago"
            )
        else:
            self.stdout.write("   Last Health Check: Never")

        if page.last_error_message:
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠️  Last Error: {page.last_error_message[:100]}..."
                )
            )

    def _show_message_stats(self, page):
        """Show message statistics."""

        stats = self._get_message_stats(page)

        self.stdout.write(f'\\n💬 Messages (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Inbound: {stats["inbound"]} | Outbound: {stats["outbound"]}'
        )
        self.stdout.write(f'   Sent: {stats["sent"]} | Failed: {stats["failed"]}')
        self.stdout.write(
            f'   Text: {stats["text"]} | Media: {stats["media"]} | Templates: {stats["templates"]}'
        )

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed messages')
            )

    def _show_webhook_stats(self, page):
        """Show webhook statistics."""

        stats = self._get_webhook_stats(page)

        self.stdout.write(f'\\n🔗 Webhooks (last {self.options["hours"]}h):')
        self.stdout.write(f'   Total Events: {stats["total"]}')
        self.stdout.write(
            f'   Processed: {stats["processed"]} | Failed: {stats["failed"]}'
        )
        self.stdout.write(
            f'   Messages: {stats["message_events"]} | Postbacks: {stats["postback_events"]}'
        )
        self.stdout.write(
            f'   Deliveries: {stats["delivery_events"]} | Reads: {stats["read_events"]}'
        )

        if stats["failed"] > 0:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  {stats["failed"]} failed webhook events')
            )

    def _show_user_stats(self, page):
        """Show user statistics."""

        stats = self._get_user_stats(page)

        self.stdout.write("\\n👥 Users:")
        self.stdout.write(f'   Total: {stats["total"]}')
        self.stdout.write(
            f'   Active (last {self.options["hours"]}h): {stats["active"]}'
        )
        self.stdout.write(f'   New (last {self.options["hours"]}h): {stats["new"]}')
        self.stdout.write(f'   Linked to Customers: {stats["linked_customers"]}')

    def _show_flow_stats(self, page):
        """Show conversation flow statistics."""

        stats = self._get_flow_stats(page)

        self.stdout.write("\\n🔄 Conversation Flows:")
        self.stdout.write(f'   Total Flows: {stats["total_flows"]}')
        self.stdout.write(f'   Active Flows: {stats["active_flows"]}')
        self.stdout.write(
            f'   Flow Executions (last {self.options["hours"]}h): {stats["executions"]}'
        )
        self.stdout.write(f'   Completion Rate: {stats["completion_rate"]:.1f}%')

        if stats["top_flows"]:
            self.stdout.write("   Top Flows:")
            for flow_name, usage in stats["top_flows"][:3]:
                self.stdout.write(f"     • {flow_name}: {usage} executions")

    def _show_error_details(self, page):
        """Show detailed error information."""

        errors = self._get_error_info(page)

        if errors["recent_errors"]:
            self.stdout.write("\\n❌ Recent Errors:")
            for error in errors["recent_errors"][:5]:
                self.stdout.write(
                    f'   • {error["timestamp"]}: {error["message"][:100]}...'
                )

    def _get_message_stats(self, page):
        """Get message statistics for a page."""

        messages = FacebookMessage.objects.filter(
            page=page, created_at__gte=self.time_window
        )

        total = messages.count()
        inbound = messages.filter(direction="inbound").count()
        outbound = messages.filter(direction="outbound").count()
        sent = messages.filter(status="sent").count()
        failed = messages.filter(status="failed").count()
        text = messages.filter(message_type="text").count()
        media = messages.filter(
            message_type__in=["image", "video", "audio", "file"]
        ).count()
        templates = messages.filter(message_type="template").count()

        return {
            "total": total,
            "inbound": inbound,
            "outbound": outbound,
            "sent": sent,
            "failed": failed,
            "text": text,
            "media": media,
            "templates": templates,
        }

    def _get_webhook_stats(self, page):
        """Get webhook statistics for a page."""

        events = FacebookWebhookEvent.objects.filter(
            page=page, created_at__gte=self.time_window
        )

        total = events.count()
        processed = events.filter(status="processed").count()
        failed = events.filter(status="failed").count()
        message_events = events.filter(event_type="message").count()
        postback_events = events.filter(event_type="messaging_postbacks").count()
        delivery_events = events.filter(event_type="message_deliveries").count()
        read_events = events.filter(event_type="message_reads").count()

        return {
            "total": total,
            "processed": processed,
            "failed": failed,
            "message_events": message_events,
            "postback_events": postback_events,
            "delivery_events": delivery_events,
            "read_events": read_events,
        }

    def _get_user_stats(self, page):
        """Get user statistics for a page."""

        all_users = FacebookUser.objects.filter(page=page)
        active_users = all_users.filter(last_interaction_at__gte=self.time_window)
        new_users = all_users.filter(created_at__gte=self.time_window)
        linked_customers = all_users.filter(customer__isnull=False)

        return {
            "total": all_users.count(),
            "active": active_users.count(),
            "new": new_users.count(),
            "linked_customers": linked_customers.count(),
        }

    def _get_flow_stats(self, page):
        """Get conversation flow statistics for a page."""

        all_flows = FacebookConversationFlow.objects.filter(page=page)
        active_flows = all_flows.filter(is_active=True)

        # Get flows with recent activity
        recent_flows = all_flows.filter(last_used_at__gte=self.time_window)

        total_executions = sum(flow.usage_count for flow in recent_flows)
        total_completions = sum(flow.completion_count for flow in recent_flows)

        completion_rate = 0
        if total_executions > 0:
            completion_rate = (total_completions / total_executions) * 100

        # Top flows by usage
        top_flows = [
            (flow.name, flow.usage_count)
            for flow in all_flows.order_by("-usage_count")[:5]
        ]

        return {
            "total_flows": all_flows.count(),
            "active_flows": active_flows.count(),
            "executions": total_executions,
            "completion_rate": completion_rate,
            "top_flows": top_flows,
        }

    def _get_error_info(self, page):
        """Get error information for a page."""

        # Failed webhook events
        failed_webhooks = FacebookWebhookEvent.objects.filter(
            page=page, status="failed", created_at__gte=self.time_window
        ).order_by("-created_at")

        # Failed messages
        failed_messages = FacebookMessage.objects.filter(
            page=page, status="failed", created_at__gte=self.time_window
        ).order_by("-created_at")

        errors = []

        # Add webhook errors
        for event in failed_webhooks:
            errors.append(
                {
                    "type": "webhook",
                    "timestamp": event.created_at.isoformat(),
                    "message": event.error_message,
                }
            )

        # Add message errors
        for message in failed_messages:
            errors.append(
                {
                    "type": "message",
                    "timestamp": message.created_at.isoformat(),
                    "message": message.error_message,
                }
            )

        # Sort by timestamp
        errors.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "recent_errors": errors,
            "webhook_errors": failed_webhooks.count(),
            "message_errors": failed_messages.count(),
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
