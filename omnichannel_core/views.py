"""
Custom authentication views for the omnichannel core.
"""

from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy


class CustomLoginView(LoginView):
    """Custom login view that ensures proper redirect to dashboard."""

    def get_success_url(self):
        """Override to force redirect to dashboard."""
        # First check if there's a 'next' parameter
        next_url = self.get_redirect_url()
        if next_url:
            return next_url

        # Force redirect to dashboard for agent users
        if hasattr(self.request.user, "agent_profile"):
            return reverse_lazy("agent_hub:dashboard")

        # Default fallback
        return reverse_lazy("admin:index")
