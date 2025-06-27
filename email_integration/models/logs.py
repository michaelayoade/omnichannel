from django.db import models

from ..enums import PollStatus
from .accounts import EmailAccount

__all__ = ["EmailPollLog"]


class EmailPollLog(models.Model):
    account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name="poll_logs",
    )
    status = models.CharField(max_length=20, choices=PollStatus.choices)
    messages_found = models.IntegerField(default=0)
    messages_processed = models.IntegerField(default=0)
    messages_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    poll_duration = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_poll_logs"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Poll {self.account.email_address} - {self.get_status_display()}"
