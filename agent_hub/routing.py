from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/conversations/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.ConversationConsumer.as_asgi(),
    ),
    re_path(r"ws/agent/status/$", consumers.AgentStatusConsumer.as_asgi()),
    re_path(r"ws/agent/notifications/$", consumers.NotificationConsumer.as_asgi()),
]
