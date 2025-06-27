import json

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    WhatsAppBusinessAccount,
    WhatsAppContact,
    WhatsAppMediaFile,
    WhatsAppMessage,
    WhatsAppRateLimit,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)


@admin.register(WhatsAppBusinessAccount)
class WhatsAppBusinessAccountAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "display_phone_number",
        "business_account_id",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "business_account_id", "phone_number"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "is_active")}),
        (
            "WhatsApp Configuration",
            {
                "fields": (
                    "business_account_id",
                    "phone_number_id",
                    "phone_number",
                    "display_phone_number",
                )
            },
        ),
        (
            "API Configuration",
            {
                "fields": ("access_token", "app_id", "app_secret"),
                "classes": ("collapse",),
            },
        ),
        (
            "Webhook Configuration",
            {"fields": ("webhook_verify_token",), "classes": ("collapse",)},
        ),
        ("Rate Limiting", {"fields": ("rate_limit_per_second", "rate_limit_per_hour")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = [
        "profile_name",
        "phone_number",
        "wa_id",
        "business_account",
        "customer_link",
        "is_opted_in",
        "last_message_at",
    ]
    list_filter = [
        "business_account",
        "is_business_verified",
        "is_opted_in",
        "last_message_at",
        "created_at",
    ]
    search_fields = ["profile_name", "phone_number", "wa_id"]
    readonly_fields = ["created_at", "updated_at"]

    def customer_link(self, obj):
        if obj.customer:
            url = reverse("admin:customers_customer_change", args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, obj.customer.full_name)
        return "-"

    customer_link.short_description = "Customer"


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = [
        "wa_message_id",
        "contact",
        "direction",
        "message_type",
        "status",
        "content_preview",
        "timestamp",
    ]
    list_filter = [
        "business_account",
        "direction",
        "message_type",
        "status",
        "timestamp",
        "created_at",
    ]
    search_fields = ["wa_message_id", "contact__profile_name", "content"]
    readonly_fields = [
        "wa_message_id",
        "timestamp",
        "sent_at",
        "delivered_at",
        "read_at",
        "failed_at",
        "created_at",
        "updated_at",
        "raw_payload_display",
    ]

    fieldsets = (
        (
            "Message Information",
            {
                "fields": (
                    "business_account",
                    "contact",
                    "wa_message_id",
                    "direction",
                    "message_type",
                    "status",
                )
            },
        ),
        ("Content", {"fields": ("content",)}),
        (
            "Media Information",
            {
                "fields": (
                    "media_url",
                    "media_id",
                    "media_filename",
                    "media_mime_type",
                    "media_size",
                    "media_sha256",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Status Tracking",
            {
                "fields": (
                    "timestamp",
                    "sent_at",
                    "delivered_at",
                    "read_at",
                    "failed_at",
                )
            },
        ),
        (
            "Error Information",
            {"fields": ("error_code", "error_message"), "classes": ("collapse",)},
        ),
        ("Raw Data", {"fields": ("raw_payload_display",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def content_preview(self, obj):
        if obj.content:
            return obj.content[:50] + ("..." if len(obj.content) > 50 else "")
        return "-"

    content_preview.short_description = "Content"

    def raw_payload_display(self, obj):
        if obj.raw_payload:
            return format_html("<pre>{}</pre>", json.dumps(obj.raw_payload, indent=2))
        return "-"

    raw_payload_display.short_description = "Raw Payload"


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "language",
        "category",
        "status",
        "quality_score",
        "business_account",
        "created_at",
    ]
    list_filter = ["business_account", "category", "status", "language"]
    search_fields = ["name", "category"]
    readonly_fields = ["created_at", "updated_at", "components_display"]

    fieldsets = (
        (
            "Template Information",
            {"fields": ("business_account", "name", "category", "language", "status")},
        ),
        ("Quality", {"fields": ("quality_score",)}),
        ("Components", {"fields": ("components_display",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def components_display(self, obj):
        if obj.components:
            return format_html("<pre>{}</pre>", json.dumps(obj.components, indent=2))
        return "-"

    components_display.short_description = "Components"


@admin.register(WhatsAppWebhookEvent)
class WhatsAppWebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "event_type",
        "processing_status",
        "business_account",
        "retry_count",
        "created_at",
        "processed_at",
    ]
    list_filter = [
        "event_type",
        "processing_status",
        "business_account",
        "created_at",
        "processed_at",
    ]
    search_fields = ["webhook_id", "event_type"]
    readonly_fields = ["created_at", "processed_at", "payload_display"]

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "business_account",
                    "event_type",
                    "webhook_id",
                    "processing_status",
                    "retry_count",
                )
            },
        ),
        ("Processing", {"fields": ("processed_at", "error_message")}),
        ("Payload", {"fields": ("payload_display",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def payload_display(self, obj):
        if obj.payload:
            return format_html("<pre>{}</pre>", json.dumps(obj.payload, indent=2))
        return "-"

    payload_display.short_description = "Payload"


@admin.register(WhatsAppMediaFile)
class WhatsAppMediaFileAdmin(admin.ModelAdmin):
    list_display = [
        "filename",
        "media_id",
        "mime_type",
        "file_size_display",
        "is_downloaded",
        "business_account",
        "created_at",
    ]
    list_filter = ["business_account", "mime_type", "is_downloaded", "created_at"]
    search_fields = ["filename", "media_id"]
    readonly_fields = ["created_at", "file_size_display", "download_link"]

    fieldsets = (
        (
            "File Information",
            {
                "fields": (
                    "business_account",
                    "message",
                    "media_id",
                    "filename",
                    "mime_type",
                    "file_size_display",
                )
            },
        ),
        (
            "Download Status",
            {"fields": ("is_downloaded", "download_url", "expires_at")},
        ),
        ("File Access", {"fields": ("file_path", "download_link")}),
        ("Verification", {"fields": ("sha256",)}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "-"

    file_size_display.short_description = "File Size"

    def download_link(self, obj):
        if obj.file_path:
            return format_html(
                '<a href="{}" target="_blank">Download</a>', obj.file_path.url
            )
        return "-"

    download_link.short_description = "Download"


@admin.register(WhatsAppRateLimit)
class WhatsAppRateLimitAdmin(admin.ModelAdmin):
    list_display = [
        "business_account",
        "endpoint",
        "request_count",
        "window_start",
        "window_end",
        "is_blocked",
    ]
    list_filter = ["business_account", "endpoint", "is_blocked", "window_start"]
    readonly_fields = ["window_start", "window_end"]

    def has_add_permission(self, request):
        return False  # Rate limits are created automatically
