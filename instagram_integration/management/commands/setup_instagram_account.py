from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from instagram_integration.models import InstagramAccount
from instagram_integration.services import InstagramAPIClient


class Command(BaseCommand):
    help = "Set up a new Instagram Business Account for DM integration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--instagram-account-id",
            type=str,
            required=True,
            help="Instagram Business Account ID",
        )
        parser.add_argument(
            "--access-token",
            type=str,
            required=True,
            help="Instagram Graph API access token",
        )
        parser.add_argument(
            "--facebook-page-id",
            type=str,
            required=True,
            help="Connected Facebook Page ID",
        )
        parser.add_argument("--app-id", type=str, required=True, help="Facebook App ID")
        parser.add_argument(
            "--app-secret", type=str, required=True, help="Facebook App Secret",
        )
        parser.add_argument("--webhook-url", type=str, help="Webhook endpoint URL")
        parser.add_argument(
            "--verify-token", type=str, help="Webhook verification token",
        )
        parser.add_argument(
            "--subscribe-webhook",
            action="store_true",
            help="Subscribe to webhook events",
        )

    def handle(self, *args, **options):
        instagram_account_id = options["instagram_account_id"]
        access_token = options["access_token"]
        facebook_page_id = options["facebook_page_id"]
        app_id = options["app_id"]
        app_secret = options["app_secret"]
        webhook_url = options.get("webhook_url", "")
        verify_token = options.get(
            "verify_token", f"verify_{timezone.now().timestamp()}",
        )

        try:
            # Check if account already exists
            if InstagramAccount.objects.filter(
                instagram_business_account_id=instagram_account_id,
            ).exists():
                raise CommandError(
                    f"Instagram account {instagram_account_id} already exists",
                )

            # Create account record
            account = InstagramAccount.objects.create(
                instagram_business_account_id=instagram_account_id,
                access_token=access_token,
                facebook_page_id=facebook_page_id,
                app_id=app_id,
                app_secret=app_secret,
                webhook_url=webhook_url,
                verify_token=verify_token,
                status="pending",
            )

            self.stdout.write(f"Created Instagram account record: {account.id}")

            # Initialize API client and fetch account info
            api_client = InstagramAPIClient(account)

            try:
                account_info = api_client.get_account_info()

                # Update account with fetched information
                account.username = account_info.get("username", "unknown")
                account.name = account_info.get("name", "")
                account.biography = account_info.get("biography", "")
                account.website = account_info.get("website", "")
                account.followers_count = account_info.get("followers_count", 0)
                account.profile_picture_url = account_info.get(
                    "profile_picture_url", "",
                )
                account.status = "active"
                account.update_health_status(True)
                account.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully set up Instagram account @{account.username} ({account.id})",
                    ),
                )

                # Subscribe to webhook if requested
                if options["subscribe_webhook"]:
                    if not webhook_url:
                        self.stdout.write(
                            self.style.WARNING(
                                "Webhook URL required for webhook subscription",
                            ),
                        )
                    else:
                        try:
                            webhook_response = api_client.subscribe_webhook(
                                webhook_url, verify_token,
                            )
                            account.webhook_subscribed = True
                            account.save()

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Successfully subscribed to webhooks: {webhook_response}",
                                ),
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Failed to subscribe to webhooks: {e!s}",
                                ),
                            )

            except Exception as e:
                account.status = "error"
                account.update_health_status(False, str(e))
                self.stdout.write(
                    self.style.ERROR(f"Failed to fetch account info: {e!s}"),
                )

        except Exception as e:
            raise CommandError(f"Failed to set up Instagram account: {e!s}")

        # Display account information
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("INSTAGRAM ACCOUNT SETUP COMPLETE")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Account ID: {account.id}")
        self.stdout.write(
            f"Instagram Business Account ID: {account.instagram_business_account_id}",
        )
        self.stdout.write(f"Username: @{account.username}")
        self.stdout.write(f"Name: {account.name}")
        self.stdout.write(f"Status: {account.status}")
        self.stdout.write(f"Health: {account.health_status}")
        self.stdout.write(f"Webhook Subscribed: {account.webhook_subscribed}")
        self.stdout.write(f"Verify Token: {account.verify_token}")
        if webhook_url:
            self.stdout.write(f"Webhook URL: {webhook_url}")
        self.stdout.write("=" * 50)
