from rest_framework.exceptions import ValidationError

from .models import AgentProfile, AgentStatus


def update_agent_status(agent_profile: AgentProfile, new_status: str) -> AgentProfile:
    """Updates the status of an agent profile.

    Args:
    ----
        agent_profile: The AgentProfile instance to update.
        new_status: The new status to set.

    Returns:
    -------
        The updated AgentProfile instance.

    Raises:
    ------
        ValidationError: If the new status is invalid.

    """
    if not new_status or new_status not in AgentStatus.values:
        raise ValidationError("Invalid status provided.")

    agent_profile.status = new_status
    agent_profile.save(update_fields=["status"])
    return agent_profile
