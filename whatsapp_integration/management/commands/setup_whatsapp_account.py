from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from whatsapp_integration.models import WhatsAppBusinessAccount
from whatsapp_integration.services.whatsapp_api import (
    WhatsAppAPIError,
    WhatsAppBusinessAPI,
)


class Command(BaseCommand):
    help = "Set up a new WhatsApp Business Account"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name", type=str, required=True, help="Business account name"
        )

        parser.add_argument(
            "--business-account-id",
            type=str,
            required=True,
            help="WhatsApp Business Account ID",
        )

        parser.add_argument(
            "--phone-number-id",
            type=str,
            required=True,
            help="WhatsApp Phone Number ID",
        )

        parser.add_argument(
            "--access-token", type=str, required=True, help="WhatsApp Access Token"
        )

        parser.add_argument(
            "--webhook-verify-token",
            type=str,
            required=True,
            help="Webhook verify token",
        )

        parser.add_argument("--app-id", type=str, required=True, help="Facebook App ID")

        parser.add_argument(
            "--app-secret", type=str, required=True, help="Facebook App Secret"
        )

        parser.add_argument(
            "--test-connection",
            action="store_true",
            help="Test API connection before saving",
        )

    def handle(self, *args, **options):
        try:
            # Create business account instance for testing
            test_account = WhatsAppBusinessAccount(
                name=options["name"],
                business_account_id=options["business_account_id"],
                phone_number_id=options["phone_number_id"],
                access_token=options["access_token"],
                webhook_verify_token=options["webhook_verify_token"],
                app_id=options["app_id"],
                app_secret=options["app_secret"],
            )

            if options["test_connection"]:
                self.stdout.write("Testing API connection...")
                self._test_connection(test_account)

            # Save to database
            with transaction.atomic():
                # Check if account already exists
                if WhatsAppBusinessAccount.objects.filter(
                    business_account_id=options["business_account_id"]
                ).exists():
                    raise CommandError(
                        f'Business account {options["business_account_id"]} already exists'
                    )

                # Get business profile to populate phone number info
                api = WhatsAppBusinessAPI(test_account)
                try:
                    profile = api.get_business_profile()
                    test_account.phone_number = profile.get("display_phone_number", "")
                    test_account.display_phone_number = profile.get(
                        "display_phone_number", ""
                    )
                except WhatsAppAPIError as e:
                    self.stdout.write(
                        self.style.WARNING(f"Could not fetch profile: {e.message}")
                    )
                    # Continue anyway, user can update later

                # Save the account
                test_account.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ WhatsApp Business Account "{options["name"]}" created successfully!'
                    )
                )

                # Sync templates
                self.stdout.write("Syncing message templates...")
                try:
                    templates = api.get_templates()
                    from whatsapp_integration.models import WhatsAppTemplate

                    template_count = 0
                    for template_data in templates:
                        WhatsAppTemplate.objects.create(
                            business_account=test_account,
                            name=template_data["name"],
                            status=template_data["status"],
                            category=template_data["category"],
                            language=template_data["language"],
                            components=template_data.get("components", []),
                            quality_score=template_data.get("quality_score", {}).get(
                                "score", ""
                            ),
                        )
                        template_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Synced {template_count} templates")
                    )

                except WhatsAppAPIError as e:
                    self.stdout.write(
                        self.style.WARNING(f"Could not sync templates: {e.message}")
                    )

                self._show_account_info(test_account)
                self._show_next_steps()

        except Exception as e:
            raise CommandError(f"Setup failed: {str(e)}")

    def _test_connection(self, account):
        """Test API connection."""
        try:
            api = WhatsAppBusinessAPI(account)
            profile = api.get_business_profile()

            self.stdout.write(self.style.SUCCESS("✓ API connection successful"))
            self.stdout.write(f'Business name: {profile.get("verified_name", "N/A")}')
            self.stdout.write(
                f'Phone number: {profile.get("display_phone_number", "N/A")}'
            )
            self.stdout.write(
                f'Verification status: {profile.get("code_verification_status", "N/A")}'
            )

        except WhatsAppAPIError as e:
            raise CommandError(f"API connection failed: {e.message}")

    def _show_account_info(self, account):
        """Show account information."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ACCOUNT INFORMATION")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Name: {account.name}")
        self.stdout.write(f"Business Account ID: {account.business_account_id}")
        self.stdout.write(f"Phone Number ID: {account.phone_number_id}")
        self.stdout.write(f"Display Phone: {account.display_phone_number}")
        self.stdout.write(f'Status: {"Active" if account.is_active else "Inactive"}')

    def _show_next_steps(self):
        """Show next steps for setup."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("NEXT STEPS")
        self.stdout.write("=" * 60)
        self.stdout.write("1. Configure webhook URL in Facebook Developer Console:")
        self.stdout.write(
            "   https://your-domain.com/api/whatsapp/webhook/<business_account_id>/"
        )
        self.stdout.write("")
        self.stdout.write("2. Test the integration:")
        self.stdout.write(
            "   python manage.py test_whatsapp --business-account-id <id> --test-type connectivity"
        )
        self.stdout.write("")
        self.stdout.write("3. Send a test message:")
        self.stdout.write(
            "   python manage.py test_whatsapp --business-account-id <id> --test-type send-text --to <phone>"
        )
        self.stdout.write("")
        self.stdout.write("4. Monitor the integration:")
        self.stdout.write(
            "   python manage.py whatsapp_monitor --business-account-id <id>"
        )
        self.stdout.write("")
        self.stdout.write("5. Add the WhatsApp app to Django settings INSTALLED_APPS:")
        self.stdout.write('   "whatsapp_integration",')
        self.stdout.write("")
        self.stdout.write("6. Run migrations:")
        self.stdout.write("   python manage.py migrate")
