from django.urls import path

from .webhooks.handlers import WhatsAppWebhookView

app_name = "whatsapp_integration"

urlpatterns = [
    # WhatsApp webhook endpoint
    path(
        "webhook/<str:business_account_id>/",
        WhatsAppWebhookView.as_view(),
        name="webhook",
    ),
]
