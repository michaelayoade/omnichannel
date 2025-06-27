import json

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    EmailAccount,
    EmailAttachment,
    EmailBounce,
    EmailContact,
    EmailMessage,
    EmailPollLog,
    EmailRule,
    EmailTemplate,
    EmailThread,
)


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "email_address",
        "account_type",
        "status",
        "incoming_protocol",
        "health_status",
        "last_poll_at",
    ]
    list_filter = [
        "account_type",
        "status",
        "incoming_protocol",
        "auto_polling_enabled",
    ]
    search_fields = ["name", "email_address", "department"]
    readonly_fields = [
        "last_poll_at",
        "last_successful_poll_at",
        "total_emails_received",
        "total_emails_sent",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "email_address",
                    "account_type",
                    "department",
                    "status",
                ),
            },
        ),
        (
            "SMTP Configuration",
            {
                "fields": (
                    "smtp_server",
                    "smtp_port",
                    "smtp_use_tls",
                    "smtp_use_ssl",
                    "smtp_username",
                    "smtp_password",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Incoming Email Configuration",
            {
                "fields": (
                    "incoming_protocol",
                    "incoming_server",
                    "incoming_port",
                    "incoming_use_ssl",
                    "incoming_username",
                    "incoming_password",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Polling Settings",
            {
                "fields": (
                    "auto_polling_enabled",
                    "poll_frequency",
                    "max_emails_per_poll",
                ),
            },
        ),
        (
            "Display & Branding",
            {
                "fields": ("display_name", "signature", "footer"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_emails_received",
                    "total_emails_sent",
                    "last_poll_at",
                    "last_successful_poll_at",
                    "last_error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def health_status(self, obj):
        if obj.is_healthy:
            return format_html('<span style="color: green;">✓ Healthy</span>')
        else:
            return format_html('<span style="color: red;">✗ Error</span>')

    health_status.short_description = "Health"


class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0
    readonly_fields = ["filename", "content_type", "size", "is_inline", "created_at"]

    def has_add_permission(self, request, obj):
        return False


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = [
        "subject_preview",
        "from_email",
        "direction",
        "status",
        "priority",
        "account",
        "received_at",
    ]
    list_filter = [
        "account",
        "direction",
        "status",
        "priority",
        "received_at",
        "created_at",
    ]
    search_fields = ["subject", "from_email", "from_name", "plain_body"]
    readonly_fields = [
        "message_id",
        "external_message_id",
        "thread_id",
        "raw_headers_display",
        "sent_at",
        "delivered_at",
        "read_at",
        "bounced_at",
        "failed_at",
        "created_at",
        "updated_at",
    ]
    inlines = [EmailAttachmentInline]

    fieldsets = (
        (
            "Message Information",
            {
                "fields": (
                    "account",
                    "message_id",
                    "external_message_id",
                    "thread_id",
                    "direction",
                    "status",
                    "priority",
                ),
            },
        ),
        (
            "Sender/Recipient",
            {
                "fields": (
                    "from_email",
                    "from_name",
                    "to_emails",
                    "cc_emails",
                    "bcc_emails",
                    "reply_to_email",
                ),
            },
        ),
        ("Content", {"fields": ("subject", "plain_body", "html_body")}),
        (
            "Thread Information",
            {
                "fields": ("in_reply_to", "references", "thread_topic"),
                "classes": ("collapse",),
            },
        ),
        (
            "Tracking",
            {
                "fields": (
                    "received_at",
                    "sent_at",
                    "delivered_at",
                    "read_at",
                    "bounced_at",
                    "failed_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Error Information",
            {
                "fields": ("error_code", "error_message", "retry_count"),
                "classes": ("collapse",),
            },
        ),
        (
            "Raw Data",
            {
                "fields": ("raw_headers_display", "raw_message"),
                "classes": ("collapse",),
            },
        ),
        (
            "Customer Linking",
            {"fields": ("linked_customer",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def subject_preview(self, obj):
        if obj.subject:
            return obj.subject[:80] + ("..." if len(obj.subject) > 80 else "")
        return "(No Subject)"

    subject_preview.short_description = "Subject"

    def raw_headers_display(self, obj):
        if obj.raw_headers:
            return format_html("<pre>{}</pre>", json.dumps(obj.raw_headers, indent=2))
        return "-"

    raw_headers_display.short_description = "Raw Headers"


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "template_type",
        "account",
        "is_active",
        "is_global",
        "created_by",
        "created_at",
    ]
    list_filter = ["template_type", "is_active", "is_global", "account"]
    search_fields = ["name", "subject", "plain_content"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Template Information",
            {"fields": ("name", "template_type", "account", "is_active", "is_global")},
        ),
        ("Content", {"fields": ("subject", "plain_content", "html_content")}),
        (
            "Variables",
            {
                "fields": ("variables",),
                "description": "List of available template variables (JSON format)",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(EmailThread)
class EmailThreadAdmin(admin.ModelAdmin):
    list_display = [
        "subject_preview",
        "account",
        "message_count",
        "status",
        "participants_display",
        "last_message_at",
    ]
    list_filter = ["account", "status", "last_message_at"]
    search_fields = ["subject", "thread_id"]
    readonly_fields = [
        "thread_id",
        "message_count",
        "first_message_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Thread Information",
            {"fields": ("thread_id", "account", "subject", "status")},
        ),
        ("Participants", {"fields": ("participants",)}),
        (
            "Statistics",
            {"fields": ("message_count", "first_message_at", "last_message_at")},
        ),
        (
            "Customer Linking",
            {"fields": ("linked_customer",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def subject_preview(self, obj):
        return obj.subject[:60] + ("..." if len(obj.subject) > 60 else "")

    subject_preview.short_description = "Subject"

    def participants_display(self, obj):
        return ", ".join(obj.participants[:3]) + (
            "..." if len(obj.participants) > 3 else ""
        )

    participants_display.short_description = "Participants"


@admin.register(EmailContact)
class EmailContactAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "email_address",
        "account",
        "customer_link",
        "total_emails_received",
        "total_emails_sent",
        "last_email_at",
    ]
    list_filter = ["account", "last_email_at", "created_at"]
    search_fields = [
        "display_name",
        "email_address",
        "first_name",
        "last_name",
        "organization",
    ]
    readonly_fields = [
        "total_emails_received",
        "total_emails_sent",
        "last_email_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Contact Information",
            {
                "fields": (
                    "account",
                    "email_address",
                    "display_name",
                    "first_name",
                    "last_name",
                    "organization",
                ),
            },
        ),
        ("Customer Linking", {"fields": ("customer",)}),
        (
            "Statistics",
            {
                "fields": (
                    "total_emails_received",
                    "total_emails_sent",
                    "last_email_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def customer_link(self, obj):
        if obj.customer:
            url = reverse("admin:customers_customer_change", args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, obj.customer.full_name)
        return "-"

    customer_link.short_description = "Customer"


@admin.register(EmailRule)
class EmailRuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "rule_type",
        "condition_type",
        "account",
        "is_active",
        "priority",
        "created_at",
    ]
    list_filter = ["rule_type", "condition_type", "is_active", "account"]
    search_fields = ["name", "condition_value"]

    fieldsets = (
        (
            "Rule Information",
            {"fields": ("name", "account", "rule_type", "is_active", "priority")},
        ),
        ("Conditions", {"fields": ("condition_type", "condition_value")}),
        (
            "Actions",
            {
                "fields": ("action_data",),
                "description": "Action configuration in JSON format",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(EmailBounce)
class EmailBounceAdmin(admin.ModelAdmin):
    list_display = [
        "bounced_email",
        "bounce_type",
        "bounce_reason_preview",
        "bounce_timestamp",
        "message_link",
    ]
    list_filter = ["bounce_type", "bounce_timestamp"]
    search_fields = ["bounced_email", "bounce_reason"]
    readonly_fields = ["created_at"]

    def bounce_reason_preview(self, obj):
        return obj.bounce_reason[:100] + ("..." if len(obj.bounce_reason) > 100 else "")

    bounce_reason_preview.short_description = "Reason"

    def message_link(self, obj):
        url = reverse(
            "admin:email_integration_emailmessage_change", args=[obj.message.id],
        )
        return format_html('<a href="{}">View Message</a>', url)

    message_link.short_description = "Message"


@admin.register(EmailPollLog)
class EmailPollLogAdmin(admin.ModelAdmin):
    list_display = [
        "account",
        "status",
        "messages_found",
        "messages_processed",
        "messages_failed",
        "poll_duration",
        "started_at",
    ]
    list_filter = ["status", "account", "started_at"]
    readonly_fields = ["started_at", "completed_at", "poll_duration"]

    fieldsets = (
        (
            "Poll Information",
            {
                "fields": (
                    "account",
                    "status",
                    "started_at",
                    "completed_at",
                    "poll_duration",
                ),
            },
        ),
        (
            "Results",
            {"fields": ("messages_found", "messages_processed", "messages_failed")},
        ),
        ("Error Information", {"fields": ("error_message",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return False  # Poll logs are created automatically


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        "filename",
        "content_type",
        "size_display",
        "is_inline",
        "message_link",
        "created_at",
    ]
    list_filter = ["content_type", "is_inline", "created_at"]
    search_fields = ["filename", "message__subject"]
    readonly_fields = ["created_at", "size_display"]

    def size_display(self, obj):
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size / (1024 * 1024):.1f} MB"

    size_display.short_description = "Size"

    def message_link(self, obj):
        url = reverse(
            "admin:email_integration_emailmessage_change", args=[obj.message.id],
        )
        return format_html('<a href="{}">View Message</a>', url)

    message_link.short_description = "Message"
