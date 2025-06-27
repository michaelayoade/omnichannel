from django.contrib.auth import get_user_model
from rest_framework import serializers

from customers.models import Customer

from .models import (
    AgentPerformanceSnapshot,
    AgentProfile,
    Conversation,
    Message,
    QuickReplyTemplate,
)

User = get_user_model()


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = "__all__"


class CustomerSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ("id", "name", "email", "first_name", "last_name")

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class QuickReplyTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickReplyTemplate
        fields = ("id", "shortcut", "content")


class AgentProfileSerializer(serializers.ModelSerializer):
    user = AgentSerializer(read_only=True)

    class Meta:
        model = AgentProfile
        fields = ("id", "user", "status", "current_conversation_count")


class AgentPerformanceSnapshotSerializer(serializers.ModelSerializer):
    agent = AgentProfileSerializer(read_only=True)

    class Meta:
        model = AgentPerformanceSnapshot
        fields = (
            "id",
            "agent",
            "period_start",
            "period_end",
            "conversations_handled",
            "messages_sent",
            "average_resolution_time",
        )


class ConversationSerializer(serializers.ModelSerializer):
    assigned_agent = AgentSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "customer",
            "channel",
            "status",
            "assigned_agent",
            "created_at",
            "last_message_at",
            "unread_count",
        )
