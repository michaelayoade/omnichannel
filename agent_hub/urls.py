from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r"conversations", views.ConversationViewSet, basename="conversation")
router.register(r"messages", views.MessageViewSet, basename="message")
router.register(r"agent-profiles", views.AgentProfileViewSet, basename="agent-profile")
router.register(
    r"quick-replies", views.QuickReplyTemplateViewSet, basename="quick-reply",
)
router.register(
    r"performance-snapshots",
    views.AgentPerformanceSnapshotViewSet,
    basename="performance-snapshot",
)

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", include(router.urls)),
]
