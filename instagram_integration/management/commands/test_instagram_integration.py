from django.core.management.base import BaseCommand, CommandError

from instagram_integration.models import InstagramAccount
from instagram_integration.services import InstagramAPIError, InstagramMessageService


class Command(BaseCommand):
    help = "Test Instagram DM integration functionality"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id", type=int, help="Instagram account ID to test",
        )
        parser.add_argument(
            "--test-user-id", type=str, help="Instagram user ID to send test message to",
        )
        parser.add_argument(
            "--test-message",
            type=str,
            default="Hello! This is a test message from the Instagram DM integration.",
            help="Test message to send",
        )
        parser.add_argument(
            "--health-check-only", action="store_true", help="Only perform health check",
        )
        parser.add_argument(
            "--list-accounts", action="store_true", help="List all Instagram accounts",
        )

    def handle(self, *args, **options):
        if options["list_accounts"]:
            self.list_accounts()
            return

        account_id = options.get("account_id")
        if not account_id:
            # Get first available account
            account = InstagramAccount.objects.first()
            if not account:
                raise CommandError(
                    "No Instagram accounts found. Run setup_instagram_account first.",
                )
        else:
            try:
                account = InstagramAccount.objects.get(id=account_id)
            except InstagramAccount.DoesNotExist:
                raise CommandError(f"Instagram account {account_id} not found")

        self.stdout.write(
            f"Testing Instagram account: @{account.username} (ID: {account.id})",
        )

        # Initialize message service
        message_service = InstagramMessageService(account)

        # Perform health check
        self.stdout.write("\n1. Performing health check...")
        try:
            is_healthy, status_message = message_service.api_client.health_check()
            if is_healthy:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Health check passed: {status_message}"),
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Health check failed: {status_message}"),
                )
                if options["health_check_only"]:
                    return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Health check error: {e!s}"))
            if options["health_check_only"]:
                return

        if options["health_check_only"]:
            return

        # Test API connectivity
        self.stdout.write("\n2. Testing API connectivity...")
        try:
            account_info = message_service.api_client.get_account_info()
            self.stdout.write(self.style.SUCCESS("✓ API connectivity successful"))
            self.stdout.write(
                f'  Account: @{account_info.get("username")} ({account_info.get("followers_count")} followers)',
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ API connectivity failed: {e!s}"))
            return

        # Test conversations retrieval
        self.stdout.write("\n3. Testing conversation retrieval...")
        try:
            conversations = message_service.api_client.get_conversations(limit=5)
            conversation_count = len(conversations.get("data", []))
            self.stdout.write(
                self.style.SUCCESS(f"✓ Retrieved {conversation_count} conversations"),
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"⚠ Conversation retrieval failed: {e!s}"),
            )

        # Test message sending if user ID provided
        test_user_id = options.get("test_user_id")
        if test_user_id:
            self.stdout.write(f"\n4. Testing message sending to user {test_user_id}...")
            try:
                # Get or create Instagram user
                instagram_user = message_service.get_or_create_user(test_user_id)
                self.stdout.write(f"  Target user: {instagram_user.display_name}")

                # Send test message
                test_message = options["test_message"]
                message = message_service.send_text_message(
                    instagram_user, test_message,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Test message sent successfully (ID: {message.message_id})",
                    ),
                )
                self.stdout.write(f"  Status: {message.status}")

            except InstagramAPIError as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Message sending failed: {e!s}"),
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Unexpected error: {e!s}"))
        else:
            self.stdout.write(
                "\n4. Skipping message sending test (no --test-user-id provided)",
            )

        # Display account statistics
        self.stdout.write("\n5. Account Statistics:")
        self.stdout.write(f"  Total messages sent: {account.total_messages_sent}")
        self.stdout.write(
            f"  Total messages received: {account.total_messages_received}",
        )
        self.stdout.write(f"  Total story replies: {account.total_story_replies}")
        self.stdout.write(f"  Webhook subscribed: {account.webhook_subscribed}")
        self.stdout.write(f"  Last health check: {account.last_health_check}")

        # Display recent messages
        self.stdout.write("\n6. Recent Messages:")
        recent_messages = account.messages.order_by("-timestamp")[:5]
        if recent_messages:
            for msg in recent_messages:
                direction_symbol = "→" if msg.direction == "outbound" else "←"
                self.stdout.write(
                    f'  {direction_symbol} {msg.timestamp.strftime("%Y-%m-%d %H:%M")} '
                    f"{msg.instagram_user.display_name}: {msg.text[:50]}...",
                )
        else:
            self.stdout.write("  No recent messages found")

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("INSTAGRAM INTEGRATION TEST COMPLETE")
        self.stdout.write("=" * 50)

    def list_accounts(self):
        """List all Instagram accounts."""
        accounts = InstagramAccount.objects.all().order_by("-created_at")

        if not accounts:
            self.stdout.write("No Instagram accounts found.")
            return

        self.stdout.write("Instagram Accounts:")
        self.stdout.write("=" * 80)

        for account in accounts:
            status_color = (
                self.style.SUCCESS if account.is_healthy else self.style.ERROR
            )

            self.stdout.write(f"ID: {account.id}")
            self.stdout.write(f"Username: @{account.username}")
            self.stdout.write(f"Name: {account.name}")
            self.stdout.write(
                f"Instagram Business Account ID: {account.instagram_business_account_id}",
            )
            self.stdout.write(status_color(f"Status: {account.status}"))
            self.stdout.write(status_color(f"Health: {account.health_status}"))
            self.stdout.write(f'Webhook: {"✓" if account.webhook_subscribed else "✗"}')
            self.stdout.write(f"Messages Sent: {account.total_messages_sent}")
            self.stdout.write(f"Messages Received: {account.total_messages_received}")
            self.stdout.write(
                f'Created: {account.created_at.strftime("%Y-%m-%d %H:%M")}',
            )
            self.stdout.write("-" * 80)
