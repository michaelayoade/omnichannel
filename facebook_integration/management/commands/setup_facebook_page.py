import requests
from django.core.management.base import BaseCommand, CommandError

from facebook_integration.models import FacebookPage
from facebook_integration.services.facebook_api import (
    FacebookGraphAPI,
    FacebookMessengerService,
)


class Command(BaseCommand):
    help = "Setup and configure a Facebook page for Messenger integration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id", type=str, required=True, help="Facebook Page ID",
        )

        parser.add_argument(
            "--page-access-token",
            type=str,
            required=True,
            help="Long-lived page access token",
        )

        parser.add_argument("--app-id", type=str, required=True, help="Facebook App ID")

        parser.add_argument(
            "--app-secret", type=str, required=True, help="Facebook App Secret",
        )

        parser.add_argument(
            "--verify-token",
            type=str,
            help="Webhook verification token (will generate random if not provided)",
        )

        parser.add_argument("--webhook-url", type=str, help="Webhook URL (optional)")

        parser.add_argument(
            "--configure-profile",
            action="store_true",
            help="Configure Messenger profile settings",
        )

        parser.add_argument(
            "--test-connection",
            action="store_true",
            help="Test connection to Facebook API",
        )

    def handle(self, *args, **options):
        try:
            # Create or update Facebook page
            page = self._create_or_update_page(options)

            # Test connection if requested
            if options["test_connection"]:
                self._test_connection(page)

            # Configure profile if requested
            if options["configure_profile"]:
                self._configure_messenger_profile(page)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully configured Facebook page: {page.page_name}",
                ),
            )

        except Exception as e:
            raise CommandError(f"Setup failed: {e!s}")

    def _create_or_update_page(self, options):
        """Create or update Facebook page configuration."""
        page_id = options["page_id"]
        page_access_token = options["page_access_token"]
        app_id = options["app_id"]
        app_secret = options["app_secret"]
        verify_token = options.get("verify_token") or self._generate_verify_token()
        webhook_url = options.get("webhook_url", "")

        # Fetch page information from Facebook
        self.stdout.write("Fetching page information from Facebook...")
        page_info = self._fetch_page_info(page_access_token)

        # Create or update page
        page, created = FacebookPage.objects.update_or_create(
            page_id=page_id,
            defaults={
                "page_name": page_info.get("name", f"Page {page_id}"),
                "page_username": page_info.get("username", ""),
                "page_category": page_info.get("category", ""),
                "page_description": page_info.get("about", ""),
                "page_access_token": page_access_token,
                "app_id": app_id,
                "app_secret": app_secret,
                "verify_token": verify_token,
                "webhook_url": webhook_url,
                "status": "active",
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} page: {page.page_name} ({page.page_id})")
        self.stdout.write(f"Verify token: {verify_token}")

        return page

    def _fetch_page_info(self, access_token):
        """Fetch page information from Facebook Graph API."""
        url = "https://graph.facebook.com/v18.0/me"
        params = {
            "access_token": access_token,
            "fields": "id,name,username,category,about",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise CommandError(f"Failed to fetch page info: {e}")

    def _generate_verify_token(self):
        """Generate a random verification token."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(32))

    def _test_connection(self, page):
        """Test connection to Facebook API."""
        self.stdout.write("Testing Facebook API connection...")

        try:
            api = FacebookGraphAPI(page)
            success, response = api.get_messenger_profile()

            if success:
                self.stdout.write(self.style.SUCCESS("✓ Connection test successful"))
                page.update_health_status(True)
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                self.stdout.write(
                    self.style.ERROR(f"✗ Connection test failed: {error_msg}"),
                )
                page.update_health_status(False, error_msg)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Connection test failed: {e}"))
            page.update_health_status(False, str(e))

    def _configure_messenger_profile(self, page):
        """Configure basic Messenger profile settings."""
        self.stdout.write("Configuring Messenger profile...")

        try:
            messenger_service = FacebookMessengerService(page)

            # Default configuration
            config_data = {
                "greeting_text": f"Hello! Welcome to {page.page_name}. How can we help you today?",
                "get_started_payload": "GET_STARTED",
                "persistent_menu": [
                    {
                        "type": "postback",
                        "title": "Get Started",
                        "payload": "GET_STARTED",
                    },
                    {"type": "postback", "title": "Help", "payload": "HELP"},
                ],
                "ice_breakers": [
                    {"question": "How can I help you?", "payload": "HELP"},
                    {
                        "question": "Tell me more about your services",
                        "payload": "SERVICES",
                    },
                ],
            }

            success = messenger_service.configure_page_settings(config_data)

            if success:
                self.stdout.write(
                    self.style.SUCCESS("✓ Messenger profile configured successfully"),
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠ Some Messenger profile settings may not have been applied",
                    ),
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Messenger profile configuration failed: {e}"),
            )
