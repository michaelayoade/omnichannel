"""Celery configuration with security best practices for Omnichannel MVP."""

import os

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omnichannel_core.settings.dev")

# Create Celery app with security settings
app = Celery("omnichannel")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Celery security settings
app.conf.update(
    # Security settings
    security_key=settings.SECRET_KEY,
    worker_disable_rate_limits=False,
    task_time_limit=90 * 60,  # 90 minutes max task execution time
    task_soft_time_limit=60 * 60,  # 60 minutes soft limit (sends exception)
    worker_max_tasks_per_child=1000,  # Prevent memory leaks
    worker_hijack_root_logger=False,  # Don't hijack root logger
    task_create_missing_queues=True,
    task_default_queue="default",
    # Result settings
    result_backend=settings.CELERY_RESULT_BACKEND,
    result_expires=60 * 60 * 24 * 7,  # Results expire in 1 week
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIME_ZONE,
    enable_utc=True,
    # Retry settings
    task_acks_late=True,  # Tasks are acknowledged after execution
    task_reject_on_worker_lost=True,  # Reject tasks when worker terminates
    # Logging
    worker_log_format="%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
    worker_task_log_format=(
        "%(asctime)s [%(process)d] [%(levelname)s] "
        "[%(task_name)s(%(task_id)s)] %(message)s"
    ),
)

# Define scheduled tasks
app.conf.beat_schedule = {
    "poll-email-accounts-every-15-minutes": {
        "task": "email_integration.tasks.polling.poll_all_email_accounts",
        "schedule": 60 * 15,  # Every 15 minutes
        "args": (),
        "options": {"expires": 60 * 14},  # Expires in 14 minutes
    },
}


@app.task(bind=True)
def debug_task(self):
    """Task for debugging Celery setup."""
