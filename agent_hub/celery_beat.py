from datetime import timedelta

# This schedule should be included in the main project's settings.
CELERY_BEAT_SCHEDULE = {
    "update-agent-performance-snapshots": {
        "task": "agent_hub.tasks.update_agent_performance_snapshots",
        "schedule": timedelta(hours=1),
    },
}
