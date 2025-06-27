from django.db import models
from django.utils import timezone


class FacebookPage(models.Model):
    """Facebook Page configuration for Messenger integration."""

    PAGE_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("error", "Error"),
        ("pending", "Pending Setup"),
    ]

    # Basic Information
    page_id = models.CharField(
        max_length=100, unique=True, help_text="Facebook Page ID"
    )
    page_name = models.CharField(max_length=255, help_text="Page display name")
    page_username = models.CharField(
        max_length=100, blank=True, help_text="Page username (@page)"
    )
    page_category = models.CharField(max_length=100, blank=True)
    page_description = models.TextField(blank=True)

    # Access Tokens
    page_access_token = models.TextField(help_text="Long-lived page access token")
    app_id = models.CharField(max_length=100, help_text="Facebook App ID")
    app_secret = models.CharField(max_length=255, help_text="Facebook App Secret")

    # Webhook Configuration
    webhook_url = models.URLField(blank=True, help_text="Webhook endpoint URL")
    verify_token = models.CharField(
        max_length=255, help_text="Webhook verification token"
    )
    webhook_subscribed = models.BooleanField(default=False)

    # Status and Health
    status = models.CharField(
        max_length=20, choices=PAGE_STATUS_CHOICES, default="pending"
    )
    is_healthy = models.BooleanField(default=False)
    last_health_check = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)

    # Settings
    auto_reply_enabled = models.BooleanField(default=True)
    welcome_message_enabled = models.BooleanField(default=True)
    get_started_enabled = models.BooleanField(default=True)
    persistent_menu_enabled = models.BooleanField(default=True)

    # Statistics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_messages_received = models.PositiveIntegerField(default=0)
    total_conversations = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["page_id"]),
            models.Index(fields=["status", "is_healthy"]),
        ]

    def __str__(self):
        return f"{self.page_name} ({self.page_id})"

    @property
    def health_status(self):
        """Get human-readable health status."""
        if self.is_healthy:
            return "Healthy"
        elif self.last_error_message:
            return f"Error: {self.last_error_message[:50]}..."
        return "Unknown"

    def update_health_status(self, is_healthy, error_message=None):
        """Update page health status."""
        self.is_healthy = is_healthy
        self.last_health_check = timezone.now()
        self.last_error_message = error_message or ""
        self.save(
            update_fields=["is_healthy", "last_health_check", "last_error_message"]
        )


class FacebookUser(models.Model):
    """Facebook Messenger user profile information."""

    # Facebook Information
    psid = models.CharField(max_length=100, unique=True, help_text="Page-scoped ID")
    page = models.ForeignKey(
        FacebookPage, on_delete=models.CASCADE, related_name="users"
    )

    # Profile Information
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    profile_pic = models.URLField(blank=True)
    locale = models.CharField(max_length=10, blank=True)
    timezone = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)

    # Customer Linking
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="facebook_profiles",
    )

    # Status
    user_status = models.CharField(max_length=50, default="active")
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    is_subscribed = models.BooleanField(default=True)

    # Statistics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_messages_received = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_interaction_at"]
        unique_together = ["psid", "page"]
        indexes = [
            models.Index(fields=["psid", "page"]),
            models.Index(fields=["page", "-last_interaction_at"]),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.psid})"

    @property
    def display_name(self):
        """Get display name for the user."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return f"User {self.psid[:8]}"

    @property
    def full_name(self):
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def update_last_interaction(self):
        """Update last interaction timestamp."""
        self.last_interaction_at = timezone.now()
        self.save(update_fields=["last_interaction_at"])


class FacebookMessage(models.Model):
    """Facebook Messenger message."""

    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("file", "File"),
        ("sticker", "Sticker"),
        ("location", "Location"),
        ("quick_reply", "Quick Reply"),
        ("postback", "Postback"),
        ("template", "Template"),
        ("fallback", "Fallback"),
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
    facebook_message_id = models.CharField(max_length=100, blank=True)

    # Relationships
    page = models.ForeignKey(
        FacebookPage, on_delete=models.CASCADE, related_name="messages"
    )
    facebook_user = models.ForeignKey(
        FacebookUser, on_delete=models.CASCADE, related_name="messages"
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="facebook_messages",
    )

    # Message Details
    message_type = models.CharField(
        max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text"
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Content
    text = models.TextField(blank=True)
    payload = models.JSONField(
        default=dict, blank=True, help_text="Raw message payload"
    )
    quick_reply_payload = models.CharField(max_length=1000, blank=True)

    # Attachments
    attachment_url = models.URLField(blank=True)
    attachment_type = models.CharField(max_length=50, blank=True)
    attachment_payload = models.JSONField(default=dict, blank=True)

    # Delivery Tracking
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
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["page", "facebook_user", "-created_at"]),
            models.Index(fields=["conversation", "-created_at"]),
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["message_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.message_type} from {self.facebook_user.display_name}"

    @property
    def has_attachment(self):
        """Check if message has attachment."""
        return bool(self.attachment_url)

    @property
    def is_template_message(self):
        """Check if message is a template."""
        return self.message_type == "template"

    def mark_as_sent(self, facebook_message_id=None):
        """Mark message as sent."""
        self.status = "sent"
        self.sent_at = timezone.now()
        if facebook_message_id:
            self.facebook_message_id = facebook_message_id
        self.save(update_fields=["status", "sent_at", "facebook_message_id"])

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


class FacebookTemplate(models.Model):
    """Facebook Messenger message templates."""

    TEMPLATE_TYPE_CHOICES = [
        ("button", "Button Template"),
        ("generic", "Generic Template"),
        ("list", "List Template"),
        ("receipt", "Receipt Template"),
        ("airline_boardingpass", "Airline Boarding Pass"),
        ("airline_checkin", "Airline Check-in"),
        ("airline_itinerary", "Airline Itinerary"),
        ("airline_update", "Airline Update"),
    ]

    # Template Information
    name = models.CharField(max_length=255, unique=True)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES)
    description = models.TextField(blank=True)

    # Template Configuration
    template_data = models.JSONField(help_text="Template structure and content")
    variables = models.JSONField(
        default=list, blank=True, help_text="Available variables"
    )

    # Settings
    is_active = models.BooleanField(default=True)
    is_global = models.BooleanField(default=False, help_text="Available to all pages")
    page = models.ForeignKey(
        FacebookPage,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="templates",
    )

    # Usage Statistics
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["template_type", "is_active"]),
            models.Index(fields=["page", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.template_type})"

    def increment_usage(self):
        """Increment template usage count."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at"])


class FacebookWebhookEvent(models.Model):
    """Facebook webhook event log."""

    EVENT_TYPE_CHOICES = [
        ("message", "Message"),
        ("messaging_postbacks", "Postback"),
        ("messaging_optins", "Opt-in"),
        ("messaging_referrals", "Referral"),
        ("messaging_handovers", "Handover"),
        ("messaging_policy_enforcement", "Policy Enforcement"),
        ("messaging_account_linking", "Account Linking"),
        ("messaging_checkout_updates", "Checkout Updates"),
        ("messaging_pre_checkouts", "Pre-checkout"),
        ("messaging_payments", "Payments"),
        ("message_deliveries", "Delivery"),
        ("message_reads", "Read Receipt"),
        ("messaging_game_plays", "Game Play"),
        ("standby", "Standby"),
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
    page = models.ForeignKey(
        FacebookPage, on_delete=models.CASCADE, related_name="webhook_events"
    )

    # Event Data
    raw_data = models.JSONField(help_text="Raw webhook event data")
    processed_data = models.JSONField(default=dict, blank=True)

    # Processing Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Related Objects
    facebook_user = models.ForeignKey(
        FacebookUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_events",
    )
    facebook_message = models.ForeignKey(
        FacebookMessage,
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
            models.Index(fields=["page", "event_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} event for {self.page.page_name}"

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


class FacebookConversationFlow(models.Model):
    """Facebook Messenger conversation flows and automation."""

    FLOW_TYPE_CHOICES = [
        ("welcome", "Welcome Flow"),
        ("lead_generation", "Lead Generation"),
        ("customer_service", "Customer Service"),
        ("onboarding", "User Onboarding"),
        ("survey", "Survey/Feedback"),
        ("booking", "Booking/Appointment"),
        ("faq", "FAQ/Help"),
        ("custom", "Custom Flow"),
    ]

    TRIGGER_TYPE_CHOICES = [
        ("get_started", "Get Started Button"),
        ("keyword", "Keyword Match"),
        ("postback", "Postback Payload"),
        ("quick_reply", "Quick Reply"),
        ("referral", "Referral"),
        ("manual", "Manual Trigger"),
    ]

    # Flow Information
    name = models.CharField(max_length=255)
    flow_type = models.CharField(max_length=30, choices=FLOW_TYPE_CHOICES)
    description = models.TextField(blank=True)

    # Page Association
    page = models.ForeignKey(
        FacebookPage, on_delete=models.CASCADE, related_name="conversation_flows"
    )

    # Trigger Configuration
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE_CHOICES)
    trigger_value = models.CharField(
        max_length=1000, blank=True, help_text="Keyword, payload, etc."
    )

    # Flow Configuration
    flow_steps = models.JSONField(help_text="Flow steps and logic")
    variables = models.JSONField(default=dict, blank=True)

    # Settings
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(
        default=0, help_text="Higher number = higher priority"
    )

    # Statistics
    usage_count = models.PositiveIntegerField(default=0)
    completion_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["page", "trigger_type", "is_active"]),
            models.Index(fields=["flow_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.page.page_name}"

    @property
    def completion_rate(self):
        """Calculate flow completion rate."""
        if self.usage_count == 0:
            return 0
        return (self.completion_count / self.usage_count) * 100

    def increment_usage(self):
        """Increment flow usage count."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at"])

    def increment_completion(self):
        """Increment flow completion count."""
        self.completion_count += 1
        self.save(update_fields=["completion_count"])


class FacebookUserState(models.Model):
    """User conversation state tracking."""

    # User and Page
    facebook_user = models.OneToOneField(
        FacebookUser, on_delete=models.CASCADE, related_name="conversation_state"
    )

    # Current State
    current_flow = models.ForeignKey(
        FacebookConversationFlow,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_users",
    )
    current_step = models.CharField(max_length=100, blank=True)
    state_data = models.JSONField(default=dict, blank=True)

    # Context
    context_variables = models.JSONField(default=dict, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    # Handover
    in_handover = models.BooleanField(default=False)
    handover_app_id = models.CharField(max_length=100, blank=True)
    handover_metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["current_flow", "-updated_at"]),
            models.Index(fields=["in_handover"]),
        ]

    def __str__(self):
        return f"State for {self.facebook_user.display_name}"

    def reset_state(self):
        """Reset user conversation state."""
        self.current_flow = None
        self.current_step = ""
        self.state_data = {}
        self.context_variables = {}
        self.save()

    def update_state(self, flow=None, step=None, data=None, variables=None):
        """Update user conversation state."""
        if flow is not None:
            self.current_flow = flow
        if step is not None:
            self.current_step = step
        if data is not None:
            self.state_data.update(data)
        if variables is not None:
            self.context_variables.update(variables)
        self.last_message_at = timezone.now()
        self.save()


class FacebookPageConfiguration(models.Model):
    """Facebook Page configuration settings."""

    # Page Reference
    page = models.OneToOneField(
        FacebookPage, on_delete=models.CASCADE, related_name="configuration"
    )

    # Messenger Profile Settings
    welcome_message = models.TextField(blank=True)
    get_started_payload = models.CharField(max_length=1000, default="GET_STARTED")

    # Persistent Menu
    persistent_menu = models.JSONField(default=list, blank=True)

    # Greeting Text
    greeting_text = models.TextField(blank=True, max_length=160)

    # Ice Breakers
    ice_breakers = models.JSONField(default=list, blank=True)

    # Domain Whitelist
    whitelisted_domains = models.JSONField(default=list, blank=True)

    # Account Linking
    account_linking_url = models.URLField(blank=True)

    # Settings
    is_configured = models.BooleanField(default=False)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Configuration for {self.page.page_name}"

    def mark_as_synced(self):
        """Mark configuration as synced with Facebook."""
        self.is_configured = True
        self.last_sync_at = timezone.now()
        self.save(update_fields=["is_configured", "last_sync_at"])
