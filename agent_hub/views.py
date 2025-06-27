from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import services
from .models import (
    AgentPerformanceSnapshot,
    AgentProfile,
    Conversation,
    Message,
    QuickReplyTemplate,
)
from .serializers import (
    AgentPerformanceSnapshotSerializer,
    AgentProfileSerializer,
    ConversationSerializer,
    MessageSerializer,
    QuickReplyTemplateSerializer,
)


class ConversationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows conversations to be viewed or edited.
    """

    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the conversations
        for the currently authenticated user.
        """
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Conversation.objects.all()
        return Conversation.objects.filter(assigned_agent=user)


class MessageViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and creating messages within a conversation.
    """

    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter messages by the conversation_id query parameter.
        conversation_id = self.request.query_params.get("conversation_id")
        if conversation_id:
            # Ensure the user has access to this conversation before showing messages.
            if Conversation.objects.filter(
                id=conversation_id, assigned_agent__user=self.request.user
            ).exists():
                return Message.objects.filter(conversation_id=conversation_id)
        return (
            Message.objects.none()
        )  # Return no messages if no valid conversation is specified

    def perform_create(self, serializer):
        """
        Set the message direction to outbound and associate the agent.
        """
        conversation = serializer.validated_data["conversation"]
        try:
            agent_profile = AgentProfile.objects.get(user=self.request.user)
        except AgentProfile.DoesNotExist:
            raise PermissionDenied("You do not have an agent profile.")

        if conversation.assigned_agent != agent_profile:
            raise PermissionDenied("You are not assigned to this conversation.")

        serializer.save(direction="outbound", sender_agent=agent_profile)


class AgentProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A viewset for viewing and managing agent profiles.
    """

    serializer_class = AgentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return the agent profile for the currently authenticated user.
        """
        return AgentProfile.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="set-status")
    def set_status(self, request):
        """
        Custom action to update the agent's status.
        """
        agent_profile = self.get_queryset().first()
        if not agent_profile:
            return Response(
                {"error": "Agent profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get("status")
        try:
            services.update_agent_status(agent_profile, new_status)
        except ValidationError as e:
            return Response({"detail": e.detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(agent_profile)
        return Response(serializer.data)


class QuickReplyTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A viewset for listing available quick reply templates.
    """

    serializer_class = QuickReplyTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the quick reply templates
        for the currently authenticated user.
        """
        return QuickReplyTemplate.objects.filter(agent=self.request.user).order_by(
            "title"
        )


@login_required
def dashboard(request):
    """
    Renders the main agent dashboard page.
    """
    return render(request, "agent_hub/dashboard.html")


class AgentPerformanceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A viewset for viewing agent performance snapshots.
    """

    serializer_class = AgentPerformanceSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all performance snapshots
        for the currently authenticated user's agent profile.
        """
        return AgentPerformanceSnapshot.objects.filter(
            agent__user=self.request.user
        ).order_by("-period_start")
