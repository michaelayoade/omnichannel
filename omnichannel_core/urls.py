"""URL configuration for omnichannel_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/

Examples
--------
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from .health import health_check, readiness_check
from .views import CustomLoginView
from .views_auth import CookieTokenObtainPairView, CookieTokenRefreshView

urlpatterns = [
    # Admin and authentication
    path("admin/", admin.site.urls),
    path("accounts/login/", CustomLoginView.as_view(), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),

    # Health check endpoints for monitoring
    path("healthz/", health_check, name="health_check"),
    path("readyz/", readiness_check, name="readiness_check"),

    # Auth endpoints
    path(
        "api/auth/token/",
        CookieTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        CookieTokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # API endpoints
    path("api/whatsapp/", include("whatsapp_integration.urls")),
    path("api/facebook/", include("facebook_integration.urls")),
    path("api/agent_hub/", include("agent_hub.urls")),
    path("api/", include("conversations.urls")), # conversations and messages
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
