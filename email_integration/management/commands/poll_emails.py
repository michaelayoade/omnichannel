from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from email_integration.channels.services.imap_service import IMAPService
from email_integration.models import EmailAccount


class Command(BaseCommand):
    help = "Manually poll email accounts for new messages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id", type=int, help="Specific email account ID to poll",
        )

        parser.add_argument(
            "--email-address", type=str, help="Email address of account to poll",
        )

        parser.add_argument(
            "--max-emails",
            type=int,
            default=50,
            help="Maximum number of emails to process (default: 50)",
        )

        parser.add_argument(
            "--all-accounts", action="store_true", help="Poll all active email accounts",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force polling even if account polling is disabled",
        )

    def handle(self, *args, **options):
        try:
            if options["all_accounts"]:
                self._poll_all_accounts(options)
            else:
                if not options["account_id"] and not options["email_address"]:
                    raise CommandError(
                        "Either --account-id, --email-address, or --all-accounts is "
                        "required",
                    )

                self._poll_single_account(options)

        except Exception as e:
            raise CommandError(f"Polling failed: {e!s}")

    def _poll_single_account(self, options):
        """Poll a single email account."""
        try:
            # Get email account
            if options["account_id"]:
                account = EmailAccount.objects.get(id=options["account_id"])
            else:
                account = EmailAccount.objects.get(
                    email_address=options["email_address"],
                )

            # Check if polling is enabled (unless forced)
            if not options["force"] and not account.auto_polling_enabled:
                self.stdout.write(
                    self.style.WARNING(
                        f"Polling disabled for {account.email_address}. "
                        f"Use --force to override.",
                    ),
                )
                return

            if account.status != "active":
                self.stdout.write(
                    self.style.WARNING(
                        f"Account {account.email_address} is not active "
                        f"(status: {account.status})",
                    ),
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"Polling account: {account.name} ({account.email_address})",
                ),
            )

            # Start polling
            start_time = timezone.now()
            imap_service = IMAPService(account)
            poll_log = imap_service.poll_emails(max_emails=options["max_emails"])

            # Display results
            duration = (timezone.now() - start_time).total_seconds()

            self.stdout.write("\n--- Polling Results ---")
            self.stdout.write(f"Status: {poll_log.get_status_display()}")
            self.stdout.write(f"Messages found: {poll_log.messages_found}")
            self.stdout.write(f"Messages processed: {poll_log.messages_processed}")
            self.stdout.write(f"Messages failed: {poll_log.messages_failed}")
            self.stdout.write(f"Duration: {duration:.2f} seconds")

            if poll_log.error_message:
                self.stdout.write(f"Error: {poll_log.error_message}")

            if poll_log.status == "success":
                self.stdout.write(
                    self.style.SUCCESS("✓ Polling completed successfully"),
                )
            else:
                self.stdout.write(self.style.ERROR("✗ Polling failed or incomplete"))

        except EmailAccount.DoesNotExist:
            raise CommandError("Email account not found")

    def _poll_all_accounts(self, options):
        """Poll all active email accounts."""
        accounts = EmailAccount.objects.filter(status="active")

        if not options["force"]:
            accounts = accounts.filter(auto_polling_enabled=True)

        if not accounts.exists():
            self.stdout.write(self.style.WARNING("No accounts found for polling"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Polling {accounts.count()} email accounts..."),
        )

        total_processed = 0
        total_failed = 0
        successful_accounts = 0
        failed_accounts = 0

        for account in accounts:
            try:
                self.stdout.write(f"\nPolling {account.email_address}...")

                start_time = timezone.now()
                imap_service = IMAPService(account)
                poll_log = imap_service.poll_emails(max_emails=options["max_emails"])
                duration = (timezone.now() - start_time).total_seconds()

                self.stdout.write(
                    f"  Found: {poll_log.messages_found}, "
                    f"Processed: {poll_log.messages_processed}, "
                    f"Failed: {poll_log.messages_failed}, "
                    f"Duration: {duration:.2f}s",
                )

                total_processed += poll_log.messages_processed
                total_failed += poll_log.messages_failed

                if poll_log.status in ("success", "no_messages"):
                    successful_accounts += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ {account.email_address}"),
                    )
                else:
                    failed_accounts += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ {account.email_address}: {poll_log.error_message}",
                        ),
                    )

            except Exception as e:
                failed_accounts += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {account.email_address}: {e}"))

        # Summary
        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"Accounts polled: {accounts.count()}")
        self.stdout.write(f"Successful: {successful_accounts}")
        self.stdout.write(f"Failed: {failed_accounts}")
        self.stdout.write(f"Total messages processed: {total_processed}")
        self.stdout.write(f"Total messages failed: {total_failed}")

        if failed_accounts == 0:
            self.stdout.write(self.style.SUCCESS("✓ All accounts polled successfully"))
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ {failed_accounts} accounts had errors"),
            )
