from django.db import models

from ..enums import ConditionType, RuleType
from .accounts import EmailAccount

__all__ = ["EmailRule"]


class EmailRule(models.Model):
    account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name="rules",
    )
    name = models.CharField(max_length=200)
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)

    # Conditions
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices)
    condition_value = models.CharField(max_length=500)

    # Actions
    action_data = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_rules"
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"
