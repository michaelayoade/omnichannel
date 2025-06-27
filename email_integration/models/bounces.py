from django.db import models

from ..enums import BounceType
from .messages import EmailMessage

__all__ = ["EmailBounce"]


class EmailBounce(models.Model):
    message = models.OneToOneField(
        EmailMessage, on_delete=models.CASCADE, related_name="bounce"
    )
    bounce_type = models.CharField(max_length=20, choices=BounceType.choices)
    bounced_email = models.EmailField()
    bounce_reason = models.TextField()
    diagnostic_code = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=100, blank=True)
    bounce_timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_bounces"

    def __str__(self):
        return f"Bounce: {self.bounced_email} ({self.get_bounce_type_display()})"
