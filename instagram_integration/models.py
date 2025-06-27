from django.db import models
from django.utils import timezone


class InstagramAccount(models.Model):
    """Instagram Business Account configuration for DM integration."""

    ACCOUNT_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("error", "Error"),
        ("pending", "Pending Setup"),
    ]

    # Basic Information
    instagram_business_account_id = models.CharField(
        max_length=100, unique=True, help_text="Instagram Business Account ID",
    )
    username = models.CharField(max_length=100, help_text="Instagram username")
    name = models.CharField(max_length=255, blank=True, help_text="Display name")
    profile_picture_url = models.URLField(blank=True)
    biography = models.TextField(blank=True)
    website = models.URLField(blank=True)
    followers_count = models.PositiveIntegerField(default=0)

    # Access Tokens and App Configuration
    access_token = models.TextField(help_text="Instagram Graph API access token")
    facebook_page_id = models.CharField(
        max_length=100, help_text="Connected Facebook Page ID",
    )
    app_id = models.CharField(max_length=100, help_text="Facebook App ID")
    app_secret = models.CharField(max_length=255, help_text="Facebook App Secret")

    # Webhook Configuration
    webhook_url = models.URLField(blank=True, help_text="Webhook endpoint URL")
    verify_token = models.CharField(
        max_length=255, help_text="Webhook verification token",
    )
    webhook_subscribed = models.BooleanField(default=False)

    # Status and Health
    status = models.CharField(
        max_length=20, choices=ACCOUNT_STATUS_CHOICES, default="pending",
    )
    is_healthy = models.BooleanField(default=False)
    last_health_check = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)

    # Settings
    auto_reply_enabled = models.BooleanField(default=True)
    story_replies_enabled = models.BooleanField(default=True)

    # Statistics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_messages_received = models.PositiveIntegerField(default=0)
    total_story_replies = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["instagram_business_account_id"]),
            models.Index(fields=["status", "is_healthy"]),
        ]

    def __str__(self):
        return f"@{self.username} ({self.instagram_business_account_id})"

    @property
    def health_status(self):
        """Get human-readable health status."""
        if self.is_healthy:
            return "Healthy"
        elif self.last_error_message:
            return f"Error: {self.last_error_message[:50]}..."
        return "Unknown"

    def update_health_status(self, is_healthy, error_message=None):
        """Update account health status."""
        self.is_healthy = is_healthy
        self.last_health_check = timezone.now()
        self.last_error_message = error_message or ""
        self.save(
            update_fields=["is_healthy", "last_health_check", "last_error_message"],
        )


class InstagramUser(models.Model):
    """Instagram user profile information."""

    # Instagram Information
    instagram_user_id = models.CharField(
        max_length=100, unique=True, help_text="Instagram Scoped ID (IGSID)",
    )
    account = models.ForeignKey(
        InstagramAccount, on_delete=models.CASCADE, related_name="users",
    )

    # Profile Information
    username = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255, blank=True)
    profile_picture_url = models.URLField(blank=True)

    # Customer Linking
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instagram_profiles",
    )

    # Interaction State
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    is_following = models.BooleanField(default=False)

    # Statistics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_messages_received = models.PositiveIntegerField(default=0)
    total_story_replies = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_interaction_at"]
        unique_together = ["instagram_user_id", "account"]
        indexes = [
            models.Index(fields=["instagram_user_id", "account"]),
            models.Index(fields=["account", "-last_interaction_at"]),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.instagram_user_id})"

    @property
    def display_name(self):
        """Get display name for the user."""
        if self.name:
            return self.name
        elif self.username:
            return f"@{self.username}"
        return f"User {self.instagram_user_id[:8]}"

    def update_last_interaction(self):
        """Update last interaction timestamp."""
        self.last_interaction_at = timezone.now()
        self.save(update_fields=["last_interaction_at"])


class InstagramMessage(models.Model):
    """Instagram Direct Message."""

    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("story_reply", "Story Reply"),
        ("story_mention", "Story Mention"),
        ("media_share", "Media Share"),
        ("like", "Like"),
        ("unsupported", "Unsupported"),
    ]

    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    ]

    # Message Identification
    message_id = models.CharField(max_length=100, unique=True)
    instagram_message_id = models.CharField(max_length=100, blank=True)

    # Relationships
    account = models.ForeignKey(
        InstagramAccount, on_delete=models.CASCADE, related_name="messages",
    )
    instagram_user = models.ForeignKey(
        InstagramUser, on_delete=models.CASCADE, related_name="messages",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instagram_messages",
    )

    # Message Details
    message_type = models.CharField(
        max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Content
    text = models.TextField(blank=True)

    # Media Attachments
    media_url = models.URLField(blank=True)
    media_type = models.CharField(max_length=50, blank=True)

    # Story-specific fields
    story_id = models.CharField(
        max_length=100, blank=True, help_text="Story ID for story replies",
    )
    story_url = models.URLField(blank=True)

    # Raw payload data
    payload = models.JSONField(
        default=dict, blank=True, help_text="Raw message payload",
    )

    # Timestamps
    timestamp = models.DateTimeField(help_text="Instagram message timestamp")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Error Handling
    error_code = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["account", "instagram_user", "-timestamp"]),
            models.Index(fields=["conversation", "-timestamp"]),
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["message_type", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.message_type} from {self.instagram_user.display_name}"

    @property
    def has_media(self):
        """Check if message has media attachment."""
        return bool(self.media_url)

    @property
    def is_story_reply(self):
        """Check if message is a story reply."""
        return self.message_type == "story_reply"

    def mark_as_sent(self, instagram_message_id=None):
        """Mark message as sent."""
        self.status = "sent"
        self.sent_at = timezone.now()
        if instagram_message_id:
            self.instagram_message_id = instagram_message_id
        self.save(update_fields=["status", "sent_at", "instagram_message_id"])

    def mark_as_delivered(self):
        """Mark message as delivered."""
        self.status = "delivered"
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"])

    def mark_as_read(self):
        """Mark message as read."""
        self.status = "read"
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at"])

    def mark_as_failed(self, error_code=None, error_message=None):
        """Mark message as failed."""
        self.status = "failed"
        self.error_code = error_code or ""
        self.error_message = error_message or ""
        self.save(update_fields=["status", "error_code", "error_message"])


class InstagramWebhookEvent(models.Model):
    """Instagram webhook event log."""

    EVENT_TYPE_CHOICES = [
        ("messages", "Direct Message"),
        ("messaging_seen", "Message Read"),
        ("story_insights", "Story Insights"),
        ("unknown", "Unknown"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
        ("ignored", "Ignored"),
    ]

    # Event Information
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    account = models.ForeignKey(
        InstagramAccount, on_delete=models.CASCADE, related_name="webhook_events",
    )

    # Event Data
    raw_data = models.JSONField(help_text="Raw webhook event data")
    processed_data = models.JSONField(default=dict, blank=True)

    # Processing Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Related Objects
    instagram_user = models.ForeignKey(
        InstagramUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_events",
    )
    instagram_message = models.ForeignKey(
        InstagramMessage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_events",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "event_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} event for {self.account.username}"

    def mark_as_processed(self, processed_data=None):
        """Mark event as processed."""
        self.status = "processed"
        self.processed_at = timezone.now()
        if processed_data:
            self.processed_data = processed_data
        self.save(update_fields=["status", "processed_at", "processed_data"])

    def mark_as_failed(self, error_message):
        """Mark event as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.save(update_fields=["status", "error_message"])


class InstagramStory(models.Model):
    """Instagram Story information for story replies."""

    # Story Information
    story_id = models.CharField(max_length=100, unique=True)
    account = models.ForeignKey(
        InstagramAccount, on_delete=models.CASCADE, related_name="stories",
    )

    # Story Content
    story_url = models.URLField(blank=True)
    media_type = models.CharField(max_length=20, blank=True)  # image, video
    caption = models.TextField(blank=True)

    # Metrics
    reply_count = models.PositiveIntegerField(default=0)

    # Timestamps
    story_timestamp = models.DateTimeField(help_text="Story creation timestamp")
    expires_at = models.DateTimeField(help_text="Story expiration time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-story_timestamp"]
        indexes = [
            models.Index(fields=["account", "-story_timestamp"]),
            models.Index(fields=["story_id"]),
        ]

    def __str__(self):
        return f"Story {self.story_id} by @{self.account.username}"

    @property
    def is_expired(self):
        """Check if story has expired."""
        return timezone.now() > self.expires_at

    def increment_reply_count(self):
        """Increment story reply count."""
        self.reply_count += 1
        self.save(update_fields=["reply_count"])


class InstagramRateLimit(models.Model):
    """Track API rate limiting for Instagram accounts."""

    # Account and endpoint tracking
    account = models.ForeignKey(
        InstagramAccount, on_delete=models.CASCADE, related_name="rate_limits",
    )
    endpoint = models.CharField(max_length=100, help_text="API endpoint")

    # Rate limiting data
    calls_made = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(auto_now_add=True)
    reset_time = models.DateTimeField()

    # Limits
    call_limit = models.PositiveIntegerField(default=100)
    window_minutes = models.PositiveIntegerField(default=60)

    class Meta:
        unique_together = ["account", "endpoint"]
        indexes = [
            models.Index(fields=["account", "endpoint"]),
            models.Index(fields=["reset_time"]),
        ]

    def __str__(self):
        return f"Rate limit for {self.account.username} - {self.endpoint}"

    def can_make_call(self):
        """Check if we can make an API call."""
        now = timezone.now()

        # Reset if window has passed
        if now >= self.reset_time:
            self.calls_made = 0
            self.window_start = now
            self.reset_time = now + timezone.timedelta(minutes=self.window_minutes)
            self.save()

        return self.calls_made < self.call_limit

    def record_call(self):
        """Record an API call."""
        self.calls_made += 1
        self.save(update_fields=["calls_made"])

    def get_wait_time(self):
        """Get seconds to wait before next call."""
        if self.can_make_call():
            return 0
        return int((self.reset_time - timezone.now()).total_seconds())
