from datetime import timedelta

# This schedule should be included in the main project's settings.
# For example, in settings.py:
# from email_integration.celery_beat import CELERY_BEAT_SCHEDULE as email_integration_schedule
# CELERY_BEAT_SCHEDULE.update(email_integration_schedule)

CELERY_BEAT_SCHEDULE = {
    "poll-all-email-accounts": {
        "task": "email_integration.tasks.polling.poll_all_email_accounts",
        "schedule": timedelta(minutes=5),
    },
    "cleanup-old-emails": {
        "task": "email_integration.tasks.maintenance.cleanup_old_emails",
        "schedule": timedelta(days=1),
    },
    "update-email-statistics": {
        "task": "email_integration.tasks.maintenance.update_email_statistics",
        "schedule": timedelta(hours=6),
    },
    "process-bounced-emails": {
        "task": "email_integration.tasks.maintenance.process_bounced_emails",
        "schedule": timedelta(hours=1),
    },
    "sync-email-templates": {
        "task": "email_integration.tasks.maintenance.sync_email_templates",
        "schedule": timedelta(days=1),
    },
}
