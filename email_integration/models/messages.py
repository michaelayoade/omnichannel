from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from ..enums import MessageDirection, MessagePriority, MessageStatus
from .accounts import EmailAccount

__all__ = ["EmailMessage", "EmailAttachment"]


class EmailMessage(models.Model):
    account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name="messages"
    )
    message_id = models.CharField(max_length=255, unique=True)
    external_message_id = models.CharField(max_length=255, blank=True)
    thread_id = models.CharField(max_length=255, blank=True)

    direction = models.CharField(max_length=20, choices=MessageDirection.choices)
    status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.PENDING
    )
    priority = models.CharField(
        max_length=10, choices=MessagePriority.choices, default=MessagePriority.NORMAL
    )

    # Sender/Recipient Information
    from_email = models.EmailField()
    from_name = models.CharField(max_length=200, blank=True)
    to_emails = models.JSONField(default=list)
    cc_emails = models.JSONField(default=list, blank=True)
    bcc_emails = models.JSONField(default=list, blank=True)
    reply_to_email = models.EmailField(blank=True)

    # Message Content
    subject = models.CharField(max_length=500)
    plain_body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)

    # Thread and Reference Information
    in_reply_to = models.CharField(max_length=255, blank=True)
    references = models.TextField(blank=True)
    thread_topic = models.CharField(max_length=500, blank=True)

    # Headers and Metadata
    raw_headers = models.JSONField(default=dict, blank=True)
    raw_message = models.TextField(blank=True)

    # Tracking Information
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Error Information
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)

    # Timestamps
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Customer Linking
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_customer = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "email_messages"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["account", "-received_at"]),
            models.Index(fields=["thread_id", "-received_at"]),
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["from_email", "-received_at"]),
        ]

    def __str__(self):
        return f"{self.subject} - {self.get_direction_display()}"

    @property
    def has_attachments(self):
        return self.attachments.exists()

    @property
    def thread_messages(self):
        if self.thread_id:
            return EmailMessage.objects.filter(thread_id=self.thread_id).order_by(
                "received_at"
            )
        return EmailMessage.objects.filter(id=self.id)


class EmailAttachment(models.Model):
    message = models.ForeignKey(
        EmailMessage, on_delete=models.CASCADE, related_name="attachments"
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    content_id = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField()
    file_path = models.FileField(upload_to="email/attachments/")
    is_inline = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_attachments"

    def __str__(self):
        return f"{self.filename} ({self.message.subject})"
