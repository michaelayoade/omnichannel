from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from email_integration.channels.services.imap_service import IMAPService
from email_integration.channels.services.smtp_service import SMTPService
from email_integration.models import EmailAccount


class Command(BaseCommand):
    help = "Test email account connectivity (SMTP and IMAP/POP3)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id", type=int, help="Specific email account ID to test"
        )

        parser.add_argument(
            "--email-address", type=str, help="Email address of account to test"
        )

        parser.add_argument(
            "--test-type",
            type=str,
            choices=["smtp", "imap", "pop3", "all"],
            default="all",
            help="Type of connection to test",
        )

        parser.add_argument(
            "--send-test-email",
            action="store_true",
            help="Send a test email (requires --to-email)",
        )

        parser.add_argument(
            "--to-email", type=str, help="Email address to send test email to"
        )

    def handle(self, *args, **options):
        try:
            # Get email account
            if options["account_id"]:
                account = EmailAccount.objects.get(id=options["account_id"])
            elif options["email_address"]:
                account = EmailAccount.objects.get(
                    email_address=options["email_address"]
                )
            else:
                raise CommandError("Either --account-id or --email-address is required")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Testing account: {account.name} ({account.email_address})"
                )
            )

            # Test based on type
            if options["test_type"] in ["smtp", "all"]:
                self._test_smtp(account, options)

            if (
                options["test_type"] in ["imap", "all"]
                and account.incoming_protocol == "imap"
            ):
                self._test_imap(account)

            if (
                options["test_type"] in ["pop3", "all"]
                and account.incoming_protocol == "pop3"
            ):
                self._test_pop3(account)

        except EmailAccount.DoesNotExist:
            raise CommandError("Email account not found")
        except Exception as e:
            raise CommandError(f"Test failed: {str(e)}")

    def _test_smtp(self, account, options):
        """Test SMTP connectivity and optionally send test email."""
        self.stdout.write("\n--- Testing SMTP Connection ---")

        try:
            smtp_service = SMTPService(account)
            success, message = smtp_service.test_connection()

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ SMTP: {message}"))

                # Send test email if requested
                if options["send_test_email"]:
                    if not options["to_email"]:
                        self.stdout.write(
                            self.style.WARNING(
                                "--to-email required for sending test email"
                            )
                        )
                    else:
                        self._send_test_email(smtp_service, options["to_email"])
            else:
                self.stdout.write(self.style.ERROR(f"✗ SMTP: {message}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ SMTP Error: {e}"))

    def _test_imap(self, account):
        """Test IMAP connectivity."""
        self.stdout.write("\n--- Testing IMAP Connection ---")

        try:
            imap_service = IMAPService(account)
            success, message = imap_service.test_connection()

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ IMAP: {message}"))

                # Get folder list
                try:
                    folders = imap_service.get_folder_list()
                    self.stdout.write(f'Available folders: {", ".join(folders)}')
                except Exception as e:
                    self.stdout.write(f"Could not get folder list: {e}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ IMAP: {message}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ IMAP Error: {e}"))

    def _test_pop3(self, account):
        """Test POP3 connectivity."""
        self.stdout.write("\n--- Testing POP3 Connection ---")

        try:
            imap_service = IMAPService(account)  # Same service handles both protocols
            success, message = imap_service.test_connection()

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ POP3: {message}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ POP3: {message}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ POP3 Error: {e}"))

    def _send_test_email(self, smtp_service, to_email):
        """Send a test email."""
        self.stdout.write(f"\nSending test email to {to_email}...")

        try:
            subject = f"Test Email from {smtp_service.account.email_address}"
            plain_body = f"""
This is a test email sent from the omnichannel email integration system.

Account: {smtp_service.account.name}
Email: {smtp_service.account.email_address}
Timestamp: {timezone.now()}

If you received this email, the SMTP configuration is working correctly.
"""

            html_body = f"""
<html>
<body>
    <h2>Test Email</h2>
    <p>This is a test email sent from the omnichannel email integration system.</p>

    <h3>Account Details:</h3>
    <ul>
        <li><strong>Account:</strong> {smtp_service.account.name}</li>
        <li><strong>Email:</strong> {smtp_service.account.email_address}</li>
        <li><strong>Timestamp:</strong> {timezone.now()}</li>
    </ul>

    <p>If you received this email, the SMTP configuration is working correctly.</p>
</body>
</html>
"""

            message = smtp_service.send_email(
                to_emails=[to_email],
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Test email sent successfully: {message.message_id}"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Failed to send test email: {e}"))
