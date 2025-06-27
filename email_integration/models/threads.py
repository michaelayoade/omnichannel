from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from ..enums import ThreadStatus
from .accounts import EmailAccount

__all__ = ["EmailThread"]


class EmailThread(models.Model):
    thread_id = models.CharField(max_length=255, unique=True)
    account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name="threads",
    )
    subject = models.CharField(max_length=500)
    participants = models.JSONField(default=list)
    message_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=ThreadStatus.choices, default=ThreadStatus.OPEN,
    )

    # Customer Linking
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_customer = GenericForeignKey("content_type", "object_id")

    first_message_at = models.DateTimeField()
    last_message_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_threads"
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Thread: {self.subject}"
