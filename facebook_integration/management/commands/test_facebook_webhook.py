import requests
from django.core.management.base import BaseCommand, CommandError

from facebook_integration.models import FacebookPage


class Command(BaseCommand):
    help = "Test Facebook webhook subscription and send test messages"

    def add_arguments(self, parser):
        parser.add_argument("--page-id", type=str, help="Facebook Page ID to test")

        parser.add_argument("--webhook-url", type=str, help="Webhook URL to test")

        parser.add_argument(
            "--verify-webhook", action="store_true", help="Test webhook verification",
        )

        parser.add_argument(
            "--subscribe-webhook", action="store_true", help="Subscribe page to webhook",
        )

        parser.add_argument(
            "--test-message",
            type=str,
            help="Send a test message to specified user PSID",
        )

        parser.add_argument(
            "--recipient-psid", type=str, help="Recipient PSID for test message",
        )

        parser.add_argument(
            "--list-subscriptions",
            action="store_true",
            help="List current webhook subscriptions",
        )

    def handle(self, *args, **options):
        try:
            if options["page_id"]:
                try:
                    page = FacebookPage.objects.get(page_id=options["page_id"])
                except FacebookPage.DoesNotExist:
                    raise CommandError(f'Page {options["page_id"]} not found')
            else:
                # Use first active page
                page = FacebookPage.objects.filter(status="active").first()
                if not page:
                    raise CommandError("No active Facebook pages found")

            self.stdout.write(f"Testing page: {page.page_name} ({page.page_id})")

            # Verify webhook
            if options["verify_webhook"]:
                self._test_webhook_verification(page, options.get("webhook_url"))

            # Subscribe webhook
            if options["subscribe_webhook"]:
                self._subscribe_webhook(page)

            # List subscriptions
            if options["list_subscriptions"]:
                self._list_webhook_subscriptions(page)

            # Send test message
            if options["test_message"] and options["recipient_psid"]:
                self._send_test_message(
                    page, options["recipient_psid"], options["test_message"],
                )

        except Exception as e:
            raise CommandError(f"Test failed: {e!s}")

    def _test_webhook_verification(self, page, webhook_url=None):
        """Test webhook verification process."""
        webhook_url = webhook_url or page.webhook_url
        if not webhook_url:
            self.stdout.write(
                self.style.WARNING("No webhook URL configured for this page"),
            )
            return

        self.stdout.write(f"Testing webhook verification: {webhook_url}")

        # Test verification request
        verify_params = {
            "hub.mode": "subscribe",
            "hub.verify_token": page.verify_token,
            "hub.challenge": "test_challenge_12345",
        }

        try:
            response = requests.get(webhook_url, params=verify_params, timeout=10)

            if response.status_code == 200:
                if response.text == "test_challenge_12345":
                    self.stdout.write(
                        self.style.SUCCESS("✓ Webhook verification successful"),
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Webhook returned wrong challenge: {response.text}",
                        ),
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Webhook verification failed: {response.status_code}",
                    ),
                )

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"✗ Webhook verification error: {e}"))

    def _subscribe_webhook(self, page):
        """Subscribe page to webhook."""
        self.stdout.write("Subscribing page to webhook...")

        url = f"https://graph.facebook.com/v18.0/{page.page_id}/subscribed_apps"

        data = {
            "subscribed_fields": [
                "messages",
                "messaging_postbacks",
                "messaging_optins",
                "messaging_referrals",
                "messaging_handovers",
                "messaging_policy_enforcement",
                "message_deliveries",
                "message_reads",
            ],
            "access_token": page.page_access_token,
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS("✓ Webhook subscription successful"),
                )
                page.webhook_subscribed = True
                page.save(update_fields=["webhook_subscribed"])
            else:
                self.stdout.write(self.style.ERROR("✗ Webhook subscription failed"))

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"✗ Webhook subscription error: {e}"))

    def _list_webhook_subscriptions(self, page):
        """List current webhook subscriptions."""
        self.stdout.write("Listing webhook subscriptions...")

        url = f"https://graph.facebook.com/v18.0/{page.page_id}/subscribed_apps"
        params = {"access_token": page.page_access_token}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            subscriptions = result.get("data", [])

            if subscriptions:
                self.stdout.write("Current subscriptions:")
                for sub in subscriptions:
                    app_name = sub.get("name", "Unknown")
                    app_id = sub.get("id", "Unknown")
                    fields = sub.get("subscribed_fields", [])
                    self.stdout.write(f"  • {app_name} (ID: {app_id})")
                    self.stdout.write(f'    Fields: {", ".join(fields)}')
            else:
                self.stdout.write("No webhook subscriptions found")

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"✗ Error listing subscriptions: {e}"))

    def _send_test_message(self, page, recipient_psid, message_text):
        """Send a test message."""
        self.stdout.write(f"Sending test message to {recipient_psid}...")

        from facebook_integration.services.facebook_api import FacebookMessengerService

        try:
            messenger_service = FacebookMessengerService(page)
            message = messenger_service.send_text(recipient_psid, message_text)

            if message.status == "sent":
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Test message sent: {message.message_id}"),
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Test message failed: {message.error_message}"),
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Test message error: {e}"))
