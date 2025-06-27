from django.contrib.auth.models import User
from django.db import models

from agents.models import Agent
from communication_channels.models import ChannelContact, CommunicationChannel
from customers.models import Customer


class Conversation(models.Model):
    CONVERSATION_STATUS_CHOICES = [
        ("open", "Open"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("escalated", "Escalated"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    conversation_id = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="conversations",
    )
    channel = models.ForeignKey(
        CommunicationChannel, on_delete=models.CASCADE, related_name="conversations",
    )
    channel_contact = models.ForeignKey(
        ChannelContact, on_delete=models.CASCADE, null=True, blank=True,
    )
    assigned_agent = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    status = models.CharField(
        max_length=20, choices=CONVERSATION_STATUS_CHOICES, default="open",
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="normal",
    )
    subject = models.CharField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_bot_conversation = models.BooleanField(default=False)
    external_conversation_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["assigned_agent", "status"]),
        ]

    def __str__(self):
        return f"Conversation {self.conversation_id} - {self.customer.full_name}"

    @property
    def response_time(self):
        if self.first_response_at:
            return self.first_response_at - self.created_at
        return None

    @property
    def resolution_time(self):
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None


class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("file", "File"),
        ("audio", "Audio"),
        ("video", "Video"),
        ("location", "Location"),
        ("system", "System"),
    ]

    SENDER_TYPE_CHOICES = [
        ("customer", "Customer"),
        ("agent", "Agent"),
        ("system", "System"),
        ("bot", "Bot"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages",
    )
    message_id = models.CharField(max_length=100, unique=True)
    external_message_id = models.CharField(max_length=200, blank=True)
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    sender_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )
    sender_name = models.CharField(max_length=200, blank=True)
    message_type = models.CharField(
        max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text",
    )
    content = models.TextField()
    raw_content = models.JSONField(default=dict, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_internal_note = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender_type", "created_at"]),
        ]

    def __str__(self):
        return f"Message {self.message_id} in {self.conversation.conversation_id}"


class ConversationParticipant(models.Model):
    PARTICIPANT_ROLE_CHOICES = [
        ("customer", "Customer"),
        ("agent", "Agent"),
        ("observer", "Observer"),
        ("supervisor", "Supervisor"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=PARTICIPANT_ROLE_CHOICES)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "conversation_participants"
        unique_together = ["conversation", "user"]

    def __str__(self):
        user_display = self.user.get_full_name() or self.user.username
        return f"{user_display} in {self.conversation.conversation_id}"


class ConversationNote(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="notes",
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversation_notes"
        ordering = ["-created_at"]

    def __str__(self):
        author_name = self.author.get_full_name() or self.author.username
        return f"Note by {author_name} in {self.conversation.conversation_id}"
