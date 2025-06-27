from django.urls import path

from . import views

app_name = "instagram_integration"

urlpatterns = [
    # Webhook endpoint
    path("webhook/", views.instagram_webhook, name="webhook"),
    # Account management
    path("accounts/", views.list_instagram_accounts, name="list_accounts"),
    path(
        "accounts/<int:account_id>/status/",
        views.get_account_status,
        name="account_status",
    ),
    path(
        "accounts/<int:account_id>/health-check/",
        views.trigger_health_check,
        name="health_check",
    ),
    # Conversations
    path(
        "accounts/<int:account_id>/conversations/",
        views.get_account_conversations,
        name="conversations",
    ),
    path(
        "accounts/<int:account_id>/conversations/<str:instagram_user_id>/messages/",
        views.get_conversation_messages,
        name="conversation_messages",
    ),
    # Message sending
    path("send/text/", views.send_text_message, name="send_text_message"),
    path("send/image/", views.send_image_message, name="send_image_message"),
]
