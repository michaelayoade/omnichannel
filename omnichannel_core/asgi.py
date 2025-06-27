"""
ASGI config for omnichannel_core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

import django
from django.core.asgi import get_asgi_application

# Set the DJANGO_SETTINGS_MODULE environment variable.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omnichannel_core.settings.dev")

# Initialize Django's settings. This is the crucial step.
django.setup()

from channels.auth import AuthMiddlewareStack

# Now that Django is set up, we can import modules that depend on it.
from channels.routing import ProtocolTypeRouter, URLRouter

import agent_hub.routing
from omnichannel_core.middleware import TokenAuthMiddleware

# The http protocol type is handled by Django's standard ASGI application.
http_application = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": http_application,
        "websocket": AuthMiddlewareStack(
            TokenAuthMiddleware(URLRouter(agent_hub.routing.websocket_urlpatterns))
        ),
    }
)
