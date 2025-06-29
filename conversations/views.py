"""ViewSets for the conversations app."""

from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(viewsets.ModelViewSet):
    """CRUD and list endpoints for conversations."""

    queryset = Conversation.objects.select_related("customer", "assigned_agent", "channel").all()
    serializer_class = ConversationSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]


class MessageViewSet(viewsets.ModelViewSet):
    """CRUD endpoints for messages within a conversation."""

    serializer_class = MessageSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Restrict messages to the selected conversation if param provided."""
        conversation_id = self.request.query_params.get("conversation")
        qs = Message.objects.select_related("conversation").all()
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        return qs

