from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class CommunicationChannel(models.Model):
    CHANNEL_TYPE_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
        ("facebook", "Facebook Messenger"),
        ("telegram", "Telegram"),
        ("web_chat", "Web Chat"),
        ("phone", "Phone"),
        ("social_media", "Social Media"),
    ]

    CHANNEL_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("maintenance", "Maintenance"),
    ]

    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=CHANNEL_STATUS_CHOICES, default="active"
    )
    configuration = models.JSONField(default=dict, blank=True)
    webhook_url = models.URLField(blank=True)
    api_credentials = models.JSONField(default=dict, blank=True)
    is_inbound = models.BooleanField(default=True)
    is_outbound = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "communication_channels"
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"


class ChannelIntegration(models.Model):
    INTEGRATION_STATUS_CHOICES = [
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("error", "Error"),
        ("pending", "Pending"),
    ]

    channel = models.OneToOneField(
        CommunicationChannel, on_delete=models.CASCADE, related_name="integration"
    )
    integration_type = models.CharField(max_length=100)
    external_id = models.CharField(max_length=200, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=INTEGRATION_STATUS_CHOICES, default="pending"
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "channel_integrations"

    def __str__(self):
        return f"{self.channel.name} Integration - {self.get_status_display()}"


class ChannelContact(models.Model):
    channel = models.ForeignKey(
        CommunicationChannel, on_delete=models.CASCADE, related_name="contacts"
    )
    external_contact_id = models.CharField(max_length=200)
    contact_identifier = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, blank=True)
    profile_data = models.JSONField(default=dict, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_customer = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "channel_contacts"
        unique_together = ["channel", "external_contact_id"]

    def __str__(self):
        return f"{self.display_name or self.contact_identifier} on {self.channel.name}"
