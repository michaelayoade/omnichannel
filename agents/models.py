from django.contrib.auth.models import User
from django.db import models


class Agent(models.Model):
    AGENT_STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("away", "Away"),
        ("busy", "Busy"),
    ]

    AGENT_ROLE_CHOICES = [
        ("agent", "Agent"),
        ("supervisor", "Supervisor"),
        ("admin", "Admin"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    agent_id = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=AGENT_ROLE_CHOICES, default="agent")
    status = models.CharField(
        max_length=20, choices=AGENT_STATUS_CHOICES, default="offline",
    )
    is_active = models.BooleanField(default=True)
    max_concurrent_conversations = models.IntegerField(default=5)
    current_conversation_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agents"
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.display_name} ({self.agent_id})"

    @property
    def is_available(self):
        return (
            self.status == "online"
            and self.is_active
            and self.current_conversation_count < self.max_concurrent_conversations
        )


class AgentSkill(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=100)
    skill_level = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_skills"
        unique_together = ["agent", "skill_name"]

    def __str__(self):
        return (
            f"{self.agent.display_name} - {self.skill_name} (Level {self.skill_level})"
        )


class AgentAvailability(models.Model):
    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="availability",
    )
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "agent_availability"
        unique_together = ["agent", "weekday", "start_time"]

    def __str__(self):
        return (
            f"{self.agent.display_name} - {self.get_weekday_display()} "
            f"{self.start_time}-{self.end_time}"
        )
