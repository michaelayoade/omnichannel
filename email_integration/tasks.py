# DEPRECATED: This file has been replaced by the `email_integration.tasks` package.
# All Celery tasks have been refactored into separate modules within that package:
#
# - `sending.py`: for send_email_task
# - `polling.py`: for poll_email_account and poll_all_email_accounts
# - `rules.py`: for process_email_rules
# - `maintenance.py`: for cleanup_old_emails
#
# Please update your imports to point to the new task locations, for example:
# from email_integration.tasks.sending import send_email_task
#
# This file will be removed in a future version.
