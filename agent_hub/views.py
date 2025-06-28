from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from omnichannel_core.cache import cached_response, invalidate_model_cache
from .permissions import IsAgent, IsSupervisor, IsAdmin, IsAgentOrReadOnly, IsSupervisorOrReadOnly, IsAdminOrReadOnly

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
    """API endpoint that allows conversations to be viewed or edited."""

    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAgent]

    def get_queryset(self):
        """This view should return a list of all the conversations
        for the currently authenticated user.
        """
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Conversation.objects.all().select_related('customer', 'assigned_agent')
        return Conversation.objects.filter(assigned_agent=user).select_related('customer', 'assigned_agent')
        
    @cached_response(timeout=60, key_prefix='conversation_list')
    def list(self, request, *args, **kwargs):
        """Cache the conversation list for 60 seconds"""
        return super().list(request, *args, **kwargs)
        
    def perform_create(self, serializer):
        """When creating a conversation, invalidate related caches"""
        instance = serializer.save()
        invalidate_model_cache('conversation')
        return instance
        
    def perform_update(self, serializer):
        """When updating a conversation, invalidate related caches"""
        instance = serializer.save()
        invalidate_model_cache('conversation', instance.id)
        return instance


class MessageViewSet(viewsets.ModelViewSet):
    """A viewset for viewing and creating messages within a conversation."""

    serializer_class = MessageSerializer
    permission_classes = [IsAgent]

    def get_queryset(self):
        # Filter messages by the conversation_id query parameter.
        conversation_id = self.request.query_params.get("conversation_id")
        if conversation_id:
            # Ensure the user has access to this conversation before showing messages.
            if Conversation.objects.filter(
                id=conversation_id, assigned_agent__user=self.request.user,
            ).exists():
                return Message.objects.filter(conversation_id=conversation_id).select_related('conversation')
        return (
            Message.objects.none()
        )  # Return no messages if no valid conversation is specified
        
    @cached_response(timeout=30, key_prefix='message_list')  # Shorter timeout as messages change frequently
    def list(self, request, *args, **kwargs):
        """Cache the message list for 30 seconds"""
        return super().list(request, *args, **kwargs)
        
    def perform_create(self, serializer):
        """When creating a message, invalidate conversation and message caches"""
        instance = serializer.save()
        # Invalidate both conversation and message caches
        invalidate_model_cache('message', instance.conversation_id)
        invalidate_model_cache('conversation', instance.conversation_id)
        return instance

    def perform_create(self, serializer):
        """Set the message direction to outbound and associate the agent."""
        conversation = serializer.validated_data["conversation"]
        try:
            agent_profile = AgentProfile.objects.get(user=self.request.user)
        except AgentProfile.DoesNotExist:
            raise PermissionDenied("You do not have an agent profile.")

        if conversation.assigned_agent != agent_profile:
            raise PermissionDenied("You are not assigned to this conversation.")

        serializer.save(direction="outbound", sender_agent=agent_profile)


class AgentProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows agent profiles to be viewed."""

    queryset = AgentProfile.objects.all()
    serializer_class = AgentProfileSerializer
    permission_classes = [IsAgent]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return AgentProfile.objects.all().select_related('user')
        return AgentProfile.objects.filter(user=user).select_related('user')
    
    @cached_response(timeout=300, key_prefix='agent_profile_list')  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """Cache the agent profile list"""
        return super().list(request, *args, **kwargs)
    
    @cached_response(timeout=300, key_prefix='agent_profile_detail')
    def retrieve(self, request, *args, **kwargs):
        """Cache individual agent profile"""
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Endpoint for current user to get their own profile"""
        user = request.user
        # Don't cache this endpoint - it's personal and changes with login state
        try:
            profile = AgentProfile.objects.select_related('user').get(user=user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except AgentProfile.DoesNotExist:
            return Response(
                {"detail": "Agent profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"], url_path="set-status")
    def set_status(self, request):
        """Custom action to update the agent's status."""
        agent_profile = self.get_queryset().first()
        if not agent_profile:
            return Response(
                {"error": "Agent profile not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        try:
            services.update_agent_status(agent_profile, new_status)
        except ValidationError as e:
            return Response({"detail": e.detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(agent_profile)
        return Response(serializer.data)


class QuickReplyTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint to view Quick Reply Templates."""

    serializer_class = QuickReplyTemplateSerializer
    permission_classes = [IsAgent]

    def get_queryset(self):
        """Return only templates belonging to the current user."""
        return QuickReplyTemplate.objects.filter(agent=self.request.user).select_related('agent')
        
    @cached_response(timeout=600, key_prefix='quick_reply_list')  # Cache for 10 minutes
    def list(self, request, *args, **kwargs):
        """Cache quick reply templates as they change infrequently"""
        return super().list(request, *args, **kwargs).order_by(
            "title",
        )


@login_required
def dashboard(request):
    """Renders the main agent dashboard page."""
    return render(request, "agent_hub/dashboard.html")


class AgentPerformanceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing agent performance metrics."""

    serializer_class = AgentPerformanceSnapshotSerializer
    permission_classes = [IsSupervisor]

    def get_queryset(self):
        user = self.request.user

        # Admins and supervisors can see all performance data
        if user.is_staff or user.is_superuser:
            return AgentPerformanceSnapshot.objects.all().select_related('agent')

        # Agents can only see their own data
        return AgentPerformanceSnapshot.objects.filter(agent=user).select_related('agent')
        
    @cached_response(timeout=600, key_prefix='performance_snapshot_list')  # Cache for 10 minutes
    def list(self, request, *args, **kwargs):
        """Cache performance snapshots as they're only updated periodically"""
        return super().list(request, *args, **kwargs)
        
    @cached_response(timeout=600, key_prefix='performance_snapshot_detail')
    def retrieve(self, request, *args, **kwargs):
        """Cache individual performance snapshots"""
        return super().retrieve(request, *args, **kwargs)
