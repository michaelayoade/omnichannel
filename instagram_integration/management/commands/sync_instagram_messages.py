from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from instagram_integration.models import InstagramAccount, InstagramMessage
from instagram_integration.services import InstagramMessageService
from instagram_integration.utils import ConversationManager


class Command(BaseCommand):
    help = "Sync Instagram messages and conversations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id", type=int, help="Specific Instagram account ID to sync"
        )
        parser.add_argument(
            "--sync-conversations",
            action="store_true",
            help="Sync messages to conversation system",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=7,
            help="Number of days back to sync (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be synced without making changes",
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Force refresh of existing message data",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")
        sync_conversations = options["sync_conversations"]
        days_back = options["days_back"]
        dry_run = options["dry_run"]
        force_refresh = options["force_refresh"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Get accounts to sync
        if account_id:
            try:
                accounts = [InstagramAccount.objects.get(id=account_id)]
            except InstagramAccount.DoesNotExist:
                raise CommandError(f"Instagram account {account_id} not found")
        else:
            accounts = InstagramAccount.objects.filter(status="active").all()

        if not accounts:
            self.stdout.write("No Instagram accounts found to sync")
            return

        total_synced = 0
        total_conversations_created = 0

        for account in accounts:
            self.stdout.write(
                f"\nSyncing account: @{account.username} (ID: {account.id})"
            )

            # Initialize services
            message_service = InstagramMessageService(account)
            conversation_manager = ConversationManager() if sync_conversations else None

            try:
                # Get conversations from Instagram API
                conversations_data = message_service.api_client.get_conversations(
                    limit=50
                )
                conversations = conversations_data.get("data", [])

                self.stdout.write(
                    f"Found {len(conversations)} conversations on Instagram"
                )

                for conversation_data in conversations:
                    conversation_id = conversation_data.get("id")

                    try:
                        # Get messages for this conversation
                        messages_data = (
                            message_service.api_client.get_conversation_messages(
                                conversation_id, limit=100
                            )
                        )
                        messages = messages_data.get("data", [])

                        self.stdout.write(
                            f"  Processing {len(messages)} messages from conversation {conversation_id}"
                        )

                        for message_data in messages:
                            message_id = message_data.get("id")
                            created_time = message_data.get("created_time")

                            # Skip if message is too old
                            if created_time:
                                message_date = timezone.datetime.fromisoformat(
                                    created_time.replace("Z", "+00:00")
                                )
                                cutoff_date = timezone.now() - timedelta(days=days_back)
                                if message_date < cutoff_date:
                                    continue

                            # Check if message already exists
                            existing_message = None
                            if not force_refresh:
                                existing_message = InstagramMessage.objects.filter(
                                    instagram_message_id=message_id, account=account
                                ).first()

                            if existing_message and not force_refresh:
                                continue

                            if not dry_run:
                                try:
                                    # Process the message
                                    instagram_message = (
                                        message_service.process_incoming_message(
                                            message_data
                                        )
                                    )
                                    total_synced += 1

                                    # Sync to conversation system if requested
                                    if sync_conversations and conversation_manager:
                                        conversation, conv_message = (
                                            conversation_manager.sync_instagram_message_to_conversation(
                                                instagram_message
                                            )
                                        )
                                        if conv_message:
                                            total_conversations_created += 1

                                    self.stdout.write(
                                        f"    ✓ Synced message {message_id}"
                                    )

                                except Exception as e:
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f"    ✗ Failed to sync message {message_id}: {str(e)}"
                                        )
                                    )
                            else:
                                self.stdout.write(
                                    f"    [DRY RUN] Would sync message {message_id}"
                                )
                                total_synced += 1

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Failed to get messages for conversation {conversation_id}: {str(e)}"
                            )
                        )

                # Update account health status
                if not dry_run:
                    account.update_health_status(True)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to sync account @{account.username}: {str(e)}"
                    )
                )
                if not dry_run:
                    account.update_health_status(False, str(e))

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("INSTAGRAM MESSAGE SYNC COMPLETE")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Accounts processed: {len(accounts)}")
        self.stdout.write(f"Messages synced: {total_synced}")
        if sync_conversations:
            self.stdout.write(
                f"Conversation messages created: {total_conversations_created}"
            )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("This was a DRY RUN - no actual changes were made")
            )
        self.stdout.write("=" * 50)
