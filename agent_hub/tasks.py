from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone

from .models import (
    AgentPerformanceSnapshot,
    AgentProfile,
    Conversation,
    Message,
    MessageDirection,
)


@shared_task
def update_agent_performance_snapshots():
    """
    A periodic task to calculate and save agent performance metrics for the previous day.
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    start_time = timezone.make_aware(datetime.combine(yesterday, time.min))
    end_time = timezone.make_aware(datetime.combine(yesterday, time.max))

    agents = AgentProfile.objects.all()

    for agent in agents:
        messages_sent = Message.objects.filter(
            conversation__assigned_agent=agent.user,
            direction=MessageDirection.OUTBOUND,
            sent_at__range=(start_time, end_time),
        ).count()

        messages_received = Message.objects.filter(
            conversation__assigned_agent=agent.user,
            direction=MessageDirection.INBOUND,
            sent_at__range=(start_time, end_time),
        ).count()

        closed_conversations = Conversation.objects.filter(
            assigned_agent=agent.user,
            status="closed",
            last_message_at__range=(start_time, end_time),
        )

        total_resolution_seconds = 0
        if closed_conversations.exists():
            for conv in closed_conversations:
                resolution_delta = conv.last_message_at - conv.created_at
                total_resolution_seconds += resolution_delta.total_seconds()
            avg_resolution_seconds = (
                total_resolution_seconds / closed_conversations.count()
            )
        else:
            avg_resolution_seconds = 0

        AgentPerformanceSnapshot.objects.update_or_create(
            agent=agent.user,
            period_start=start_time,  # This key is now stable for the day
            defaults={
                "period_end": end_time,
                "conversations_closed": closed_conversations.count(),
                "messages_sent": messages_sent,
                "messages_received": messages_received,
                "response_time_avg_seconds": int(avg_resolution_seconds),
            },
        )

    return f"Updated performance snapshots for {agents.count()} agents."
