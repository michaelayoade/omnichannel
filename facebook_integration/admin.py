import json

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    FacebookConversationFlow,
    FacebookMessage,
    FacebookPage,
    FacebookPageConfiguration,
    FacebookTemplate,
    FacebookUser,
    FacebookUserState,
    FacebookWebhookEvent,
)


@admin.register(FacebookPage)
class FacebookPageAdmin(admin.ModelAdmin):
    list_display = [
        "page_name",
        "page_id",
        "status",
        "health_status_display",
        "webhook_subscribed",
        "total_messages_sent",
        "total_messages_received",
        "created_at",
    ]
    list_filter = ["status", "is_healthy", "webhook_subscribed", "created_at"]
    search_fields = ["page_name", "page_id", "page_username"]
    readonly_fields = [
        "is_healthy",
        "last_health_check",
        "total_messages_sent",
        "total_messages_received",
        "total_conversations",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "page_name",
                    "page_id",
                    "page_username",
                    "page_category",
                    "page_description",
                    "status",
                )
            },
        ),
        (
            "Access Tokens",
            {
                "fields": ("page_access_token", "app_id", "app_secret"),
                "classes": ("collapse",),
            },
        ),
        (
            "Webhook Configuration",
            {"fields": ("webhook_url", "verify_token", "webhook_subscribed")},
        ),
        (
            "Health & Status",
            {
                "fields": ("is_healthy", "last_health_check", "last_error_message"),
                "classes": ("collapse",),
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "auto_reply_enabled",
                    "welcome_message_enabled",
                    "get_started_enabled",
                    "persistent_menu_enabled",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_messages_sent",
                    "total_messages_received",
                    "total_conversations",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def health_status_display(self, obj):
        if obj.is_healthy:
            return format_html('<span style="color: green;">✓ Healthy</span>')
        else:
            return format_html('<span style="color: red;">✗ Error</span>')

    health_status_display.short_description = "Health"


@admin.register(FacebookUser)
class FacebookUserAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "psid",
        "page",
        "customer_link",
        "user_status",
        "is_subscribed",
        "last_interaction_at",
    ]
    list_filter = ["page", "user_status", "is_subscribed", "created_at"]
    search_fields = ["psid", "first_name", "last_name", "customer__full_name"]
    readonly_fields = [
        "psid",
        "total_messages_sent",
        "total_messages_received",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Facebook Information", {"fields": ("psid", "page")}),
        (
            "Profile Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "profile_pic",
                    "locale",
                    "timezone",
                    "gender",
                )
            },
        ),
        ("Customer Linking", {"fields": ("customer",)}),
        ("Status", {"fields": ("user_status", "last_interaction_at", "is_subscribed")}),
        (
            "Statistics",
            {
                "fields": ("total_messages_sent", "total_messages_received"),
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


@admin.register(FacebookMessage)
class FacebookMessageAdmin(admin.ModelAdmin):
    list_display = [
        "message_preview",
        "facebook_user",
        "direction",
        "message_type",
        "status",
        "has_attachment",
        "created_at",
    ]
    list_filter = ["page", "direction", "message_type", "status", "created_at"]
    search_fields = ["text", "facebook_user__first_name", "facebook_user__last_name"]
    readonly_fields = [
        "message_id",
        "facebook_message_id",
        "sent_at",
        "delivered_at",
        "read_at",
        "payload_display",
        "attachment_payload_display",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Message Information",
            {
                "fields": (
                    "message_id",
                    "facebook_message_id",
                    "page",
                    "facebook_user",
                    "conversation",
                    "direction",
                    "message_type",
                    "status",
                )
            },
        ),
        ("Content", {"fields": ("text", "quick_reply_payload")}),
        (
            "Attachments",
            {
                "fields": (
                    "attachment_url",
                    "attachment_type",
                    "attachment_payload_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Delivery Tracking",
            {
                "fields": ("sent_at", "delivered_at", "read_at"),
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
        ("Raw Data", {"fields": ("payload_display",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def message_preview(self, obj):
        if obj.text:
            return obj.text[:50] + ("..." if len(obj.text) > 50 else "")
        elif obj.attachment_type:
            return f"[{obj.attachment_type.title()}]"
        return f"[{obj.message_type.title()}]"

    message_preview.short_description = "Message"

    def payload_display(self, obj):
        if obj.payload:
            return format_html("<pre>{}</pre>", json.dumps(obj.payload, indent=2))
        return "-"

    payload_display.short_description = "Payload"

    def attachment_payload_display(self, obj):
        if obj.attachment_payload:
            return format_html(
                "<pre>{}</pre>", json.dumps(obj.attachment_payload, indent=2)
            )
        return "-"

    attachment_payload_display.short_description = "Attachment Payload"


@admin.register(FacebookTemplate)
class FacebookTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "template_type",
        "page",
        "is_active",
        "is_global",
        "usage_count",
        "last_used_at",
    ]
    list_filter = ["template_type", "is_active", "is_global", "page"]
    search_fields = ["name", "description"]
    readonly_fields = ["usage_count", "last_used_at", "created_at", "updated_at"]

    fieldsets = (
        (
            "Template Information",
            {
                "fields": (
                    "name",
                    "template_type",
                    "description",
                    "page",
                    "is_active",
                    "is_global",
                )
            },
        ),
        ("Template Data", {"fields": ("template_data", "variables")}),
        (
            "Usage Statistics",
            {"fields": ("usage_count", "last_used_at"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(FacebookWebhookEvent)
class FacebookWebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        "event_id",
        "event_type",
        "page",
        "status",
        "facebook_user",
        "processed_at",
        "created_at",
    ]
    list_filter = ["event_type", "status", "page", "created_at"]
    search_fields = [
        "event_id",
        "facebook_user__first_name",
        "facebook_user__last_name",
    ]
    readonly_fields = [
        "event_id",
        "raw_data_display",
        "processed_data_display",
        "processed_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Event Information", {"fields": ("event_id", "event_type", "page", "status")}),
        ("Related Objects", {"fields": ("facebook_user", "facebook_message")}),
        (
            "Processing",
            {"fields": ("processed_at", "error_message"), "classes": ("collapse",)},
        ),
        (
            "Raw Data",
            {
                "fields": ("raw_data_display", "processed_data_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def raw_data_display(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.raw_data, indent=2))

    raw_data_display.short_description = "Raw Data"

    def processed_data_display(self, obj):
        if obj.processed_data:
            return format_html(
                "<pre>{}</pre>", json.dumps(obj.processed_data, indent=2)
            )
        return "-"

    processed_data_display.short_description = "Processed Data"


@admin.register(FacebookConversationFlow)
class FacebookConversationFlowAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "flow_type",
        "trigger_type",
        "page",
        "is_active",
        "priority",
        "usage_count",
        "completion_rate_display",
    ]
    list_filter = ["flow_type", "trigger_type", "is_active", "page"]
    search_fields = ["name", "description", "trigger_value"]
    readonly_fields = [
        "usage_count",
        "completion_count",
        "completion_rate_display",
        "last_used_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Flow Information",
            {
                "fields": (
                    "name",
                    "flow_type",
                    "description",
                    "page",
                    "is_active",
                    "priority",
                )
            },
        ),
        ("Trigger Configuration", {"fields": ("trigger_type", "trigger_value")}),
        ("Flow Configuration", {"fields": ("flow_steps", "variables")}),
        (
            "Statistics",
            {
                "fields": (
                    "usage_count",
                    "completion_count",
                    "completion_rate_display",
                    "last_used_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def completion_rate_display(self, obj):
        rate = obj.completion_rate
        if rate >= 80:
            color = "green"
        elif rate >= 50:
            color = "orange"
        else:
            color = "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    completion_rate_display.short_description = "Completion Rate"


@admin.register(FacebookUserState)
class FacebookUserStateAdmin(admin.ModelAdmin):
    list_display = [
        "facebook_user",
        "current_flow",
        "current_step",
        "in_handover",
        "last_message_at",
    ]
    list_filter = ["current_flow", "in_handover", "last_message_at"]
    search_fields = ["facebook_user__first_name", "facebook_user__last_name"]
    readonly_fields = [
        "state_data_display",
        "context_variables_display",
        "handover_metadata_display",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "User State",
            {
                "fields": (
                    "facebook_user",
                    "current_flow",
                    "current_step",
                    "last_message_at",
                )
            },
        ),
        (
            "State Data",
            {
                "fields": ("state_data_display", "context_variables_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Handover",
            {
                "fields": (
                    "in_handover",
                    "handover_app_id",
                    "handover_metadata_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def state_data_display(self, obj):
        if obj.state_data:
            return format_html("<pre>{}</pre>", json.dumps(obj.state_data, indent=2))
        return "-"

    state_data_display.short_description = "State Data"

    def context_variables_display(self, obj):
        if obj.context_variables:
            return format_html(
                "<pre>{}</pre>", json.dumps(obj.context_variables, indent=2)
            )
        return "-"

    context_variables_display.short_description = "Context Variables"

    def handover_metadata_display(self, obj):
        if obj.handover_metadata:
            return format_html(
                "<pre>{}</pre>", json.dumps(obj.handover_metadata, indent=2)
            )
        return "-"

    handover_metadata_display.short_description = "Handover Metadata"


@admin.register(FacebookPageConfiguration)
class FacebookPageConfigurationAdmin(admin.ModelAdmin):
    list_display = ["page", "is_configured", "last_sync_at", "created_at"]
    list_filter = ["is_configured", "last_sync_at"]
    readonly_fields = ["is_configured", "last_sync_at", "created_at", "updated_at"]

    fieldsets = (
        ("Page Configuration", {"fields": ("page", "is_configured", "last_sync_at")}),
        (
            "Messenger Profile",
            {"fields": ("welcome_message", "greeting_text", "get_started_payload")},
        ),
        (
            "Menu & Ice Breakers",
            {"fields": ("persistent_menu", "ice_breakers"), "classes": ("collapse",)},
        ),
        (
            "Advanced Settings",
            {
                "fields": ("whitelisted_domains", "account_linking_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
