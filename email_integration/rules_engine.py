"""Reusable email rule evaluation and execution engine.

This module isolates the logic previously embedded in ``email_integration.tasks`` so it
can be shared by other communication‐channel adapters (WhatsApp, SMS, etc.).
It follows the open/closed principle: new rule types or actions can be added by
extending the public helpers without touching call-sites.
"""

from __future__ import annotations

import logging
from typing import Any

from .channels.adapters.base import BaseOutboundAdapter
from .models import EmailMessage, EmailRule, EmailTemplate

logger = logging.getLogger(__name__)

__all__ = [
    "rule_matches",
    "execute_rule",
]

# ---------------------------------------------------------------------------
# Rule evaluation helpers
# ---------------------------------------------------------------------------


def rule_matches(rule: EmailRule, message: EmailMessage) -> bool:
    """Return **True** if *rule* matches *message*.

    Rule matching is case-insensitive and covers the most common condition types.
    The implementation deliberately lives in one place so that *all* channels can
    reuse it. When additional condition types are required, simply extend the
    conditional chain below (consider refactoring to a strategy table for many
    types).
    """
    condition_type = rule.condition_type
    condition_value = (rule.condition_value or "").lower()

    # Sender-based conditions
    if condition_type == "from_contains":
        return condition_value in message.from_email.lower()
    if condition_type == "from_equals":
        return condition_value == message.from_email.lower()

    # Subject-based conditions
    if condition_type == "subject_contains":
        return condition_value in (message.subject or "").lower()
    if condition_type == "subject_equals":
        return condition_value == (message.subject or "").lower()

    # Body text conditions
    if condition_type == "body_contains":
        body_text = f"{message.plain_body} {message.html_body}".lower()
        return condition_value in body_text

    # Attachment presence
    if condition_type == "has_attachment":
        return message.has_attachments

    # Domain equality
    if condition_type == "domain_equals":
        from_domain = message.from_email.split("@")[-1].lower()
        return condition_value == from_domain

    logger.debug("Unhandled condition_type '%s' in rule %s", condition_type, rule.id)
    return False


# ---------------------------------------------------------------------------
# Rule action helpers
# ---------------------------------------------------------------------------


def execute_rule(
    adapter: BaseOutboundAdapter, rule: EmailRule, message: EmailMessage,
) -> None:
    """Execute the *rule*'s action for *message*.

    All exceptions are caught and logged so Celery tasks invoking this helper do
    not crash the worker. Extend the ``_ACTION_DISPATCH`` map to support new
    rule types without changing this function.
    """
    action_func = _ACTION_DISPATCH.get(rule.rule_type)
    if not action_func:
        logger.warning("No handler for rule_type '%s'", rule.rule_type)
        return

    try:
        action_func(adapter, message, rule.action_data or {})
    except Exception as exc:
        logger.exception(
            "Error executing rule %s on message %s: %s", rule.id, message.id, exc,
        )


# ---------------------------------------------------------------------------
# Individual action implementations (private)
# ---------------------------------------------------------------------------


def _send_auto_reply(
    adapter: BaseOutboundAdapter, message: EmailMessage, action_data: dict[str, Any],
) -> None:
    """Send an auto-reply using a stored template."""
    template_id = action_data.get("template_id")
    if not template_id:
        logger.debug("Auto-reply skipped: no template_id in action_data")
        return

    try:
        template = EmailTemplate.objects.get(id=template_id)
    except EmailTemplate.DoesNotExist:
        logger.error("Auto-reply template %s not found", template_id)
        return

    context = {
        "sender_name": message.from_name or message.from_email,
        "original_subject": message.subject,
        "account_name": message.account.display_name,
    }

    adapter.send(
        to_emails=[message.from_email],
        subject=template.subject,
        plain_body=template.plain_content,
        html_body=template.html_content,
        template_context=context,
    )


def _forward_message(
    adapter: BaseOutboundAdapter, message: EmailMessage, action_data: dict[str, Any],
) -> None:
    """Forward *message* to the addresses in *action_data['forward_to']*."""
    forward_to: list[str] = action_data.get("forward_to", [])
    if not forward_to:
        logger.debug("Forward skipped: no recipients in action_data")
        return

    # Construct forwarded email content
    subject = f"Fwd: {message.subject}"

    # Format date with fallback to N/A if not available
    date_format = '%a, %b %d, %Y at %I:%M %p'
    date_str = message.received_at.strftime(date_format) if message.received_at else 'N/A'

    forward_header = (
        f"---------- Forwarded message ---------\n"
        f"From: {message.from_name or message.from_email} <{message.from_email}>\n"
        f"Date: {date_str}\n"
        f"Subject: {message.subject}\n"
        f"To: {', '.join(message.to_emails)}\n\n"
    )

    plain_body = f"{forward_header}{message.plain_body or ''}"
    forward_header_html = forward_header.replace("\n", "<br>")
    html_body = (
        f"<blockquote>{forward_header_html}</blockquote>{message.html_body or ''}"
    )

    attachments = []
    if action_data.get("include_attachments", True):
        attachments = list(message.attachments.all())

    adapter.send(
        to_emails=forward_to,
        subject=subject,
        plain_body=plain_body,
        html_body=html_body,
        attachments=attachments,
    )


def _assign_message(
    adapter: BaseOutboundAdapter, message: EmailMessage, action_data: dict[str, Any],
) -> None:
    """Placeholder for assignment logic (e.g., to agent or queue)."""
    assigned_to = action_data.get("assigned_to")
    if not assigned_to:
        logger.debug("Assignment skipped: no 'assigned_to' specified")
        return

    # TODO: Integrate with your agent or queue system.
    logger.info("Message %s assigned to %s", message.id, assigned_to)


def _set_message_priority(
    adapter: BaseOutboundAdapter, message: EmailMessage, action_data: dict[str, Any],
) -> None:
    """Mutate *message.priority* according to *action_data['priority']*."""
    priority = action_data.get("priority", "normal")
    if priority == message.priority:
        return

    message.priority = priority
    message.save(update_fields=["priority", "updated_at"])
    logger.info("Set priority of message %s to %s", message.id, priority)


_ACTION_DISPATCH = {
    "auto_reply": _send_auto_reply,
    "forward": _forward_message,
    "assignment": _assign_message,
    "priority": _set_message_priority,
}
