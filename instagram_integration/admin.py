from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    InstagramAccount,
    InstagramMessage,
    InstagramRateLimit,
    InstagramStory,
    InstagramUser,
    InstagramWebhookEvent,
)


@admin.register(InstagramAccount)
class InstagramAccountAdmin(admin.ModelAdmin):
    list_display = [
        "username",
        "name",
        "status",
        "is_healthy",
        "webhook_subscribed",
        "total_messages_sent",
        "total_messages_received",
        "followers_count",
        "created_at",
    ]
    list_filter = ["status", "is_healthy", "webhook_subscribed", "created_at"]
    search_fields = ["username", "name", "instagram_business_account_id"]
    readonly_fields = [
        "instagram_business_account_id",
        "last_health_check",
        "last_error_message",
        "total_messages_sent",
        "total_messages_received",
        "total_story_replies",
        "health_status_display",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "username",
                    "name",
                    "instagram_business_account_id",
                    "profile_picture_url",
                    "biography",
                    "website",
                    "followers_count",
                )
            },
        ),
        (
            "API Configuration",
            {
                "fields": ("access_token", "facebook_page_id", "app_id", "app_secret"),
                "classes": ("collapse",),
            },
        ),
        (
            "Webhook Configuration",
            {"fields": ("webhook_url", "verify_token", "webhook_subscribed")},
        ),
        (
            "Status & Health",
            {
                "fields": (
                    "status",
                    "is_healthy",
                    "health_status_display",
                    "last_health_check",
                    "last_error_message",
                )
            },
        ),
        ("Settings", {"fields": ("auto_reply_enabled", "story_replies_enabled")}),
        (
            "Statistics",
            {
                "fields": (
                    "total_messages_sent",
                    "total_messages_received",
                    "total_story_replies",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def health_status_display(self, obj):
        color = "green" if obj.is_healthy else "red"
        return format_html(
            '<span style="color: {};">{}</span>', color, obj.health_status
        )

    health_status_display.short_description = "Health Status"


@admin.register(InstagramUser)
class InstagramUserAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "username",
        "account",
        "customer_link",
        "last_interaction_at",
        "total_messages_sent",
        "total_messages_received",
        "is_following",
    ]
    list_filter = ["account", "is_following", "last_interaction_at", "created_at"]
    search_fields = ["username", "name", "instagram_user_id"]
    readonly_fields = [
        "instagram_user_id",
        "total_messages_sent",
        "total_messages_received",
        "total_story_replies",
        "created_at",
        "updated_at",
    ]

    def customer_link(self, obj):
        if obj.customer:
            url = reverse("admin:customers_customer_change", args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, obj.customer)
        return "-"

    customer_link.short_description = "Customer"


@admin.register(InstagramMessage)
class InstagramMessageAdmin(admin.ModelAdmin):
    list_display = [
        "message_id",
        "account",
        "instagram_user",
        "message_type",
        "direction",
        "status",
        "timestamp",
        "conversation_link",
    ]
    list_filter = [
        "account",
        "message_type",
        "direction",
        "status",
        "timestamp",
        "created_at",
    ]
    search_fields = ["message_id", "instagram_message_id", "text"]
    readonly_fields = [
        "message_id",
        "instagram_message_id",
        "timestamp",
        "sent_at",
        "delivered_at",
        "read_at",
        "retry_count",
        "created_at",
        "updated_at",
        "message_preview",
    ]

    fieldsets = (
        (
            "Message Information",
            {
                "fields": (
                    "message_id",
                    "instagram_message_id",
                    "account",
                    "instagram_user",
                    "conversation",
                    "message_type",
                    "direction",
                    "status",
                )
            },
        ),
        ("Content", {"fields": ("message_preview", "text", "media_url", "media_type")}),
        (
            "Story Information",
            {"fields": ("story_id", "story_url"), "classes": ("collapse",)},
        ),
        ("Timestamps", {"fields": ("timestamp", "sent_at", "delivered_at", "read_at")}),
        (
            "Error Information",
            {
                "fields": ("error_code", "error_message", "retry_count"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("payload", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def message_preview(self, obj):
        if obj.text:
            return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text
        elif obj.media_url:
            return format_html(
                '<a href="{}" target="_blank">View Media</a>', obj.media_url
            )
        return "-"

    message_preview.short_description = "Preview"

    def conversation_link(self, obj):
        if obj.conversation:
            url = reverse(
                "admin:conversations_conversation_change", args=[obj.conversation.id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.conversation.id)
        return "-"

    conversation_link.short_description = "Conversation"


@admin.register(InstagramWebhookEvent)
class InstagramWebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        "event_id",
        "account",
        "event_type",
        "status",
        "processed_at",
        "created_at",
    ]
    list_filter = ["account", "event_type", "status", "processed_at", "created_at"]
    search_fields = ["event_id", "error_message"]
    readonly_fields = [
        "event_id",
        "processed_at",
        "created_at",
        "updated_at",
        "raw_data_preview",
    ]

    fieldsets = (
        (
            "Event Information",
            {"fields": ("event_id", "account", "event_type", "status", "processed_at")},
        ),
        ("Related Objects", {"fields": ("instagram_user", "instagram_message")}),
        (
            "Data",
            {
                "fields": ("raw_data_preview", "raw_data", "processed_data"),
                "classes": ("collapse",),
            },
        ),
        ("Error Information", {"fields": ("error_message",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def raw_data_preview(self, obj):
        import json

        data_str = json.dumps(obj.raw_data, indent=2)[:500]
        return format_html("<pre>{}</pre>", data_str)

    raw_data_preview.short_description = "Raw Data Preview"


@admin.register(InstagramStory)
class InstagramStoryAdmin(admin.ModelAdmin):
    list_display = [
        "story_id",
        "account",
        "reply_count",
        "story_timestamp",
        "expires_at",
        "is_expired",
    ]
    list_filter = ["account", "media_type", "story_timestamp", "expires_at"]
    search_fields = ["story_id", "caption"]
    readonly_fields = ["story_id", "is_expired", "created_at", "updated_at"]

    def is_expired(self, obj):
        return obj.is_expired

    is_expired.boolean = True
    is_expired.short_description = "Expired"


@admin.register(InstagramRateLimit)
class InstagramRateLimitAdmin(admin.ModelAdmin):
    list_display = [
        "account",
        "endpoint",
        "calls_made",
        "call_limit",
        "window_start",
        "reset_time",
        "can_make_call_display",
    ]
    list_filter = ["account", "endpoint", "reset_time"]
    readonly_fields = ["window_start", "can_make_call_display"]

    def can_make_call_display(self, obj):
        can_call = obj.can_make_call()
        color = "green" if can_call else "red"
        text = "Yes" if can_call else f"No (wait {obj.get_wait_time()}s)"
        return format_html('<span style="color: {};">{}</span>', color, text)

    can_make_call_display.short_description = "Can Make Call"
