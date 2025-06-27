import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from customers.models import Customer


class AgentStatus(models.TextChoices):
    ONLINE = "online", "Online"
    OFFLINE = "offline", "Offline"
    BUSY = "busy", "Busy"


class AgentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_profile"
    )
    status = models.CharField(
        max_length=10, choices=AgentStatus.choices, default=AgentStatus.OFFLINE
    )
    current_conversation_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"


class ChannelTypes(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    FACEBOOK = "facebook", "Facebook"
    INSTAGRAM = "instagram", "Instagram"


class ConversationStatus(models.TextChoices):
    NEW = "new", "New"
    OPEN = "open", "Open"
    PENDING = "pending", "Pending"
    CLOSED = "closed", "Closed"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.CharField(max_length=20, choices=ChannelTypes.choices)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="agent_hub_conversations"
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )
    status = models.CharField(
        max_length=10,
        choices=ConversationStatus.choices,
        default=ConversationStatus.NEW,
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    # Generic foreign key to link to specific channel accounts (e.g., EmailAccount)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    channel_account = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Conversation {self.id} with {self.customer}"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField(max_length=10, choices=MessageDirection.choices)
    body = models.TextField()
    # For simplicity, storing attachment URLs or paths in a JSON field.
    attachments = models.JSONField(default=list, blank=True)
    channel_message_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="The unique ID of the message from the source channel.",
    )
    sent_at = models.DateTimeField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"Message {self.id} in conversation {self.conversation.id}"


class QuickReplyTemplate(models.Model):
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quick_replies"
    )
    title = models.CharField(max_length=100)
    content = models.TextField()
    shortcut = models.CharField(max_length=50)

    class Meta:
        unique_together = ("agent", "shortcut")

    def __str__(self):
        return self.title


class AgentPerformanceSnapshot(models.Model):
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="performance_snapshots",
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    response_time_avg_seconds = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    messages_received = models.PositiveIntegerField(default=0)
    conversations_closed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("agent", "period_start", "period_end")
        ordering = ["-period_start"]

    def __str__(self):
        return f"Performance for {self.agent.username} from {self.period_start} to {self.period_end}"
