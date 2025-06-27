from django.db import models

from customers.models import Customer


class WhatsAppBusinessAccount(models.Model):
    name = models.CharField(max_length=200)
    business_account_id = models.CharField(max_length=100, unique=True)
    phone_number_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=20)
    display_phone_number = models.CharField(max_length=20)
    access_token = models.TextField()
    webhook_verify_token = models.CharField(max_length=100)
    app_id = models.CharField(max_length=100)
    app_secret = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    rate_limit_per_second = models.IntegerField(default=10)
    rate_limit_per_hour = models.IntegerField(default=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_business_accounts"

    def __str__(self):
        return f"{self.name} ({self.display_phone_number})"


class WhatsAppContact(models.Model):
    business_account = models.ForeignKey(
        WhatsAppBusinessAccount, on_delete=models.CASCADE, related_name="contacts",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="whatsapp_contacts",
    )
    wa_id = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20)
    profile_name = models.CharField(max_length=200, blank=True)
    is_business_verified = models.BooleanField(default=False)
    is_opted_in = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_contacts"
        unique_together = ["business_account", "wa_id"]

    def __str__(self):
        return f"{self.profile_name or self.phone_number} ({self.wa_id})"


class WhatsAppMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("audio", "Audio"),
        ("video", "Video"),
        ("document", "Document"),
        ("sticker", "Sticker"),
        ("location", "Location"),
        ("contacts", "Contacts"),
        ("template", "Template"),
        ("interactive", "Interactive"),
        ("system", "System"),
    ]

    MESSAGE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    ]

    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]

    business_account = models.ForeignKey(
        WhatsAppBusinessAccount, on_delete=models.CASCADE, related_name="messages",
    )
    contact = models.ForeignKey(
        WhatsAppContact, on_delete=models.CASCADE, related_name="messages",
    )
    wa_message_id = models.CharField(max_length=100, unique=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=MESSAGE_STATUS_CHOICES, default="pending",
    )
    content = models.TextField(blank=True)
    media_url = models.URLField(blank=True)
    media_id = models.CharField(max_length=100, blank=True)
    media_filename = models.CharField(max_length=255, blank=True)
    media_mime_type = models.CharField(max_length=100, blank=True)
    media_sha256 = models.CharField(max_length=64, blank=True)
    media_size = models.BigIntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_messages"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["contact", "-timestamp"]),
            models.Index(fields=["status", "-timestamp"]),
            models.Index(fields=["direction", "-timestamp"]),
        ]

    def __str__(self):
        return f"WhatsApp message {self.wa_message_id} - {self.get_direction_display()}"


class WhatsAppTemplate(models.Model):
    TEMPLATE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("disabled", "Disabled"),
    ]

    CATEGORY_CHOICES = [
        ("authentication", "Authentication"),
        ("marketing", "Marketing"),
        ("utility", "Utility"),
    ]

    business_account = models.ForeignKey(
        WhatsAppBusinessAccount, on_delete=models.CASCADE, related_name="templates",
    )
    name = models.CharField(max_length=512)
    status = models.CharField(max_length=20, choices=TEMPLATE_STATUS_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    language = models.CharField(max_length=10, default="en_US")
    components = models.JSONField(default=list)
    quality_score = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_templates"
        unique_together = ["business_account", "name", "language"]

    def __str__(self):
        return f"{self.name} ({self.language}) - {self.get_status_display()}"


class WhatsAppWebhookEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ("messages", "Messages"),
        ("message_status", "Message Status"),
        ("account_alerts", "Account Alerts"),
        ("business_capability_update", "Business Capability Update"),
    ]

    PROCESSING_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
        ("ignored", "Ignored"),
    ]

    business_account = models.ForeignKey(
        WhatsAppBusinessAccount,
        on_delete=models.CASCADE,
        related_name="webhook_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    webhook_id = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict)
    processing_status = models.CharField(
        max_length=20, choices=PROCESSING_STATUS_CHOICES, default="pending",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "whatsapp_webhook_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["processing_status", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return (
            f"WhatsApp webhook {self.event_type} - "
            f"{self.get_processing_status_display()}"
        )


class WhatsAppMediaFile(models.Model):
    business_account = models.ForeignKey(
        WhatsAppBusinessAccount, on_delete=models.CASCADE, related_name="media_files",
    )
    message = models.ForeignKey(
        WhatsAppMessage, on_delete=models.CASCADE, related_name="media_files",
    )
    media_id = models.CharField(max_length=100, unique=True)
    file_path = models.FileField(upload_to="whatsapp/media/")
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    is_downloaded = models.BooleanField(default=False)
    download_url = models.URLField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "whatsapp_media_files"

    def __str__(self):
        return f"Media {self.media_id} - {self.filename}"


class WhatsAppRateLimit(models.Model):
    business_account = models.ForeignKey(
        WhatsAppBusinessAccount, on_delete=models.CASCADE, related_name="rate_limits",
    )
    endpoint = models.CharField(max_length=100)
    request_count = models.IntegerField(default=0)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    is_blocked = models.BooleanField(default=False)
    reset_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "whatsapp_rate_limits"
        unique_together = ["business_account", "endpoint", "window_start"]

    def __str__(self):
        return f"Rate limit {self.endpoint} - {self.request_count} requests"
