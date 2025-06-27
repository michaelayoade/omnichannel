import json

from django.core.management.base import BaseCommand, CommandError

from whatsapp_integration.models import WhatsAppBusinessAccount
from whatsapp_integration.services.whatsapp_api import (
    WhatsAppAPIError,
    WhatsAppMessageService,
)
from whatsapp_integration.utils.phone_validator import PhoneNumberValidator


class Command(BaseCommand):
    help = "Test WhatsApp Business API integration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--business-account-id",
            type=str,
            required=True,
            help="WhatsApp Business Account ID",
        )

        parser.add_argument(
            "--to", type=str, help="Phone number to send test message to",
        )

        parser.add_argument(
            "--test-type",
            type=str,
            choices=[
                "connectivity",
                "send-text",
                "send-template",
                "profile",
                "templates",
            ],
            default="connectivity",
            help="Type of test to perform",
        )

        parser.add_argument(
            "--template-name", type=str, help="Template name for template test",
        )

        parser.add_argument(
            "--message",
            type=str,
            default="This is a test message from your WhatsApp integration.",
            help="Message content for text test",
        )

    def handle(self, *args, **options):
        try:
            # Get business account
            business_account = WhatsAppBusinessAccount.objects.get(
                business_account_id=options["business_account_id"], is_active=True,
            )

            self.stdout.write(
                self.style.SUCCESS(f"Found business account: {business_account.name}"),
            )

            # Initialize service
            message_service = WhatsAppMessageService(business_account)

            # Perform test based on type
            if options["test_type"] == "connectivity":
                self._test_connectivity(message_service)
            elif options["test_type"] == "send-text":
                self._test_send_text(message_service, options)
            elif options["test_type"] == "send-template":
                self._test_send_template(message_service, options)
            elif options["test_type"] == "profile":
                self._test_profile(message_service)
            elif options["test_type"] == "templates":
                self._test_templates(message_service)

        except WhatsAppBusinessAccount.DoesNotExist:
            raise CommandError(
                f'Business account {options["business_account_id"]} not found',
            )
        except Exception as e:
            raise CommandError(f"Test failed: {e!s}")

    def _test_connectivity(self, message_service):
        """Test basic API connectivity."""
        self.stdout.write("Testing API connectivity...")

        try:
            profile = message_service.api.get_business_profile()
            self.stdout.write(self.style.SUCCESS("✓ API connectivity successful"))
            self.stdout.write(f"Business profile: {json.dumps(profile, indent=2)}")

        except WhatsAppAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ API connectivity failed: {e.message}"),
            )
            if e.error_code:
                self.stdout.write(f"Error code: {e.error_code}")

    def _test_send_text(self, message_service, options):
        """Test sending a text message."""
        if not options["to"]:
            raise CommandError("Phone number (--to) is required for text message test")

        self.stdout.write(f'Testing text message to {options["to"]}...')

        # Validate phone number
        formatted_phone = PhoneNumberValidator.format_for_whatsapp(options["to"])
        if not formatted_phone:
            raise CommandError(f'Invalid phone number: {options["to"]}')

        self.stdout.write(f"Formatted phone number: {formatted_phone}")

        try:
            message = message_service.send_message(
                to=formatted_phone, message_type="text", content=options["message"],
            )

            self.stdout.write(self.style.SUCCESS("✓ Text message sent successfully"))
            self.stdout.write(f"Message ID: {message.wa_message_id}")
            self.stdout.write(f"Status: {message.status}")

        except WhatsAppAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to send text message: {e.message}"),
            )
            if e.error_code:
                self.stdout.write(f"Error code: {e.error_code}")

    def _test_send_template(self, message_service, options):
        """Test sending a template message."""
        if not options["to"]:
            raise CommandError("Phone number (--to) is required for template test")

        if not options["template_name"]:
            raise CommandError(
                "Template name (--template-name) is required for template test",
            )

        self.stdout.write(f'Testing template message to {options["to"]}...')

        # Validate phone number
        formatted_phone = PhoneNumberValidator.format_for_whatsapp(options["to"])
        if not formatted_phone:
            raise CommandError(f'Invalid phone number: {options["to"]}')

        try:
            message = message_service.send_message(
                to=formatted_phone,
                message_type="template",
                template_name=options["template_name"],
            )

            self.stdout.write(
                self.style.SUCCESS("✓ Template message sent successfully"),
            )
            self.stdout.write(f"Message ID: {message.wa_message_id}")
            self.stdout.write(f'Template: {options["template_name"]}')

        except WhatsAppAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to send template message: {e.message}"),
            )
            if e.error_code:
                self.stdout.write(f"Error code: {e.error_code}")

    def _test_profile(self, message_service):
        """Test getting business profile."""
        self.stdout.write("Testing business profile retrieval...")

        try:
            profile = message_service.api.get_business_profile()

            self.stdout.write(
                self.style.SUCCESS("✓ Business profile retrieved successfully"),
            )

            self.stdout.write(f'Verified name: {profile.get("verified_name")}')
            self.stdout.write(f'Display phone: {profile.get("display_phone_number")}')
            self.stdout.write(
                f'Verification status: {profile.get("code_verification_status")}',
            )

        except WhatsAppAPIError as e:
            self.stdout.write(self.style.ERROR(f"✗ Failed to get profile: {e.message}"))

    def _test_templates(self, message_service):
        """Test getting message templates."""
        self.stdout.write("Testing message templates retrieval...")

        try:
            templates = message_service.api.get_templates()

            self.stdout.write(
                self.style.SUCCESS(f"✓ Retrieved {len(templates)} templates"),
            )

            for template in templates:
                self.stdout.write(
                    f'- {template["name"]} ({template["language"]}) - '
                    f'{template["status"]}',
                )
                if template.get("quality_score"):
                    self.stdout.write(
                        f'  Quality: {template["quality_score"].get("score", "N/A")}',
                    )

        except WhatsAppAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to get templates: {e.message}"),
            )
