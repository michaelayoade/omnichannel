from django.apps import AppConfig


class AgentHubConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent_hub"

    def ready(self):
        pass
