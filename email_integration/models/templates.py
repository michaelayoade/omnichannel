from django.contrib.auth.models import User
from django.db import models

from ..enums import TemplateType
from .accounts import EmailAccount

__all__ = ["EmailTemplate"]


class EmailTemplate(models.Model):
    account = models.ForeignKey(
        EmailAccount,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    subject = models.CharField(max_length=500)
    plain_content = models.TextField(blank=True)
    html_content = models.TextField(blank=True)
    variables = models.JSONField(
        default=list, blank=True, help_text="List of template variables",
    )
    is_active = models.BooleanField(default=True)
    is_global = models.BooleanField(
        default=False, help_text="Available to all accounts",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_templates"
        unique_together = ["name", "account"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
