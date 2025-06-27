"""
Management command to migrate plaintext credentials to encrypted format.

This command handles the secure migration of existing plaintext credentials
to the new encrypted format, maintaining data integrity and security.
"""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from email_integration.config import get_config
from email_integration.models import EmailAccount
from email_integration.utils.crypto import encrypt_value
from omnichannel_core.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to encrypt plaintext credentials in EmailAccount models.
    Safely migrates existing plaintext passwords to the new encrypted format.
    """

    help = "Migrate plaintext credentials to encrypted format for email accounts"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of accounts to process in each batch",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without saving changes",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-encrypt credentials even if they appear to be already encrypted",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Check if encryption is configured
        if not get_config("ENCRYPTION_KEY"):
            raise CommandError(
                "ENCRYPTION_KEY is not configured. Encryption cannot proceed."
            )

        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        force = options["force"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE: No changes will be saved")
            )

        # Get accounts that may need migration
        # Look for accounts with settings containing passwords that don't appear to be encrypted
        accounts = self._get_accounts_for_migration(force)
        total_accounts = accounts.count()

        if total_accounts == 0:
            self.stdout.write(
                self.style.SUCCESS("No accounts found that need credential encryption")
            )
            return

        self.stdout.write(
            f"Found {total_accounts} accounts that may need credential encryption"
        )

        # Process in batches to avoid memory issues
        processed = 0
        updated = 0
        errored = 0

        start_time = time.time()

        # Process accounts in batches
        for i in range(0, total_accounts, batch_size):
            batch = accounts[i : i + batch_size]
            batch_processed, batch_updated, batch_errored = self._process_batch(
                batch, dry_run
            )

            processed += batch_processed
            updated += batch_updated
            errored += batch_errored

            # Show progress
            percent_complete = (processed / total_accounts) * 100
            self.stdout.write(
                f"Progress: {percent_complete:.1f}% ({processed}/{total_accounts})"
            )

        duration = time.time() - start_time

        # Final report
        self.stdout.write(
            self.style.SUCCESS(
                f"Migration completed in {duration:.2f} seconds\n"
                f"Accounts processed: {processed}\n"
                f"Accounts updated: {updated}\n"
                f"Accounts with errors: {errored}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "This was a dry run. To perform actual migration, run without --dry-run flag"
                )
            )

    def _get_accounts_for_migration(self, force=False):
        """
        Get accounts that need their credentials encrypted.

        Args:
            force: Whether to include accounts that might already have encrypted credentials

        Returns:
            QuerySet of EmailAccount objects
        """
        # Base query for all accounts with server settings
        query = EmailAccount.objects.exclude(server_settings={}).exclude(
            server_settings=None
        )

        if not force:
            # Try to identify accounts with plaintext credentials by looking for common patterns
            # This is imperfect but helps avoid unnecessary re-encryption
            plaintext_filter = (
                (
                    # Accounts with SMTP password that doesn't look encrypted
                    # (encrypted strings typically start with 'gAAAAA' for Fernet)
                    Q(server_settings__has_key="smtp_password")
                    & ~Q(
                        server_settings__smtp_password__startswith="gAAAAA"
                    )  # nosec B106
                )
                | (
                    # Accounts with incoming password that doesn't look encrypted
                    Q(server_settings__has_key="imap_password")
                    & ~Q(
                        server_settings__imap_password__startswith="gAAAAA"
                    )  # nosec B106
                )
                | (
                    # Accounts with POP3 password that doesn't look encrypted
                    Q(server_settings__has_key="pop3_password")
                    & ~Q(
                        server_settings__pop3_password__startswith="gAAAAA"
                    )  # nosec B106
                )
            )

            query = query.filter(plaintext_filter)

        return query

    def _process_batch(self, batch, dry_run=False):
        """
        Process a batch of accounts for credential encryption.

        Args:
            batch: Iterable of EmailAccount objects
            dry_run: Whether this is a dry run (no changes saved)

        Returns:
            Tuple of (processed, updated, errored) counts
        """
        processed = 0
        updated = 0
        errored = 0

        for account in batch:
            processed += 1

            try:
                # Use transaction to ensure atomicity
                with transaction.atomic():
                    if self._encrypt_account_credentials(account) and not dry_run:
                        account.save()
                        updated += 1
                        logger.info(
                            f"Encrypted credentials for account {account.id}",
                            extra={"account_id": account.id},
                        )
                    elif dry_run:
                        # In dry run, count as updated if changes would have been made
                        updated += 1
                        self.stdout.write(
                            f"Would encrypt credentials for account {account.id}"
                        )
                    else:
                        self.stdout.write(f"No changes needed for account {account.id}")

            except Exception as e:
                errored += 1
                logger.error(
                    f"Error encrypting credentials for account {account.id}: {str(e)}",
                    extra={"account_id": account.id},
                )
                self.stdout.write(
                    self.style.ERROR(f"Error processing account {account.id}: {str(e)}")
                )

        return processed, updated, errored

    def _encrypt_account_credentials(self, account):
        """
        Encrypt plaintext credentials for an account.

        Args:
            account: The EmailAccount object

        Returns:
            True if changes were made, False otherwise
        """
        settings = account.server_settings.copy() if account.server_settings else {}
        changes_made = False

        # SMTP password
        if "smtp_password" in settings and not settings["smtp_password"].startswith(
            "gAAAAA"
        ):
            settings["smtp_password"] = encrypt_value(settings["smtp_password"])
            changes_made = True

        # IMAP password
        if "imap_password" in settings and not settings["imap_password"].startswith(
            "gAAAAA"
        ):
            settings["imap_password"] = encrypt_value(settings["imap_password"])
            changes_made = True

        # POP3 password
        if "pop3_password" in settings and not settings["pop3_password"].startswith(
            "gAAAAA"
        ):
            settings["pop3_password"] = encrypt_value(settings["pop3_password"])
            changes_made = True

        # OAuth tokens (if present)
        if "oauth2" in settings and isinstance(settings["oauth2"], dict):
            oauth2 = settings["oauth2"]

            # Refresh token
            if "refresh_token" in oauth2 and not oauth2["refresh_token"].startswith(
                "gAAAAA"
            ):
                oauth2["refresh_token"] = encrypt_value(oauth2["refresh_token"])
                settings["oauth2"] = oauth2
                changes_made = True

            # Client secret
            if "client_secret" in oauth2 and not oauth2["client_secret"].startswith(
                "gAAAAA"
            ):
                oauth2["client_secret"] = encrypt_value(oauth2["client_secret"])
                settings["oauth2"] = oauth2
                changes_made = True

        # Update settings if changes were made
        if changes_made:
            account.server_settings = settings

        return changes_made
