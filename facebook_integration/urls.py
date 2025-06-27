from django.urls import path

from .webhooks.views import (
    FacebookWebhookView,
    facebook_test_webhook,
    facebook_webhook_endpoint,
)

app_name = "facebook_integration"

urlpatterns = [
    # Main webhook endpoint (class-based)
    path("webhook/", FacebookWebhookView.as_view(), name="webhook"),
    # Alternative webhook endpoint (function-based)
    path("webhook/simple/", facebook_webhook_endpoint, name="webhook_simple"),
    # Test webhook endpoint
    path("webhook/test/", facebook_test_webhook, name="webhook_test"),
]
