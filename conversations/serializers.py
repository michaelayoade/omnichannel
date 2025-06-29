"""Serializers for the conversations app."""

from rest_framework import serializers

from .models import Conversation, Message, ConversationParticipant, ConversationNote


class ConversationSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    class Meta:
        model = Conversation
        fields = (
            "id",
            "conversation_id",
            "customer_name",
            "last_message_preview",
            "customer",
            "channel",
            "assigned_agent",
            "status",
            "priority",
            "subject",
            "tags",
            "metadata",
            "is_bot_conversation",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "customer_name",
            "last_message_preview",
        )


    def get_customer_name(self, obj):
        return obj.customer.full_name or obj.customer.email or obj.customer.phone

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return last_msg.content[:100]
        return ""


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "message_id",
            "external_message_id",
            "sender_type",
            "sender_user",
            "sender_name",
            "message_type",
            "content",
            "raw_content",
            "attachments",
            "metadata",
            "is_internal_note",
            "delivered_at",
            "read_at",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ConversationParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationParticipant
        fields = (
            "id",
            "conversation",
            "user",
            "role",
            "joined_at",
            "left_at",
            "is_active",
        )
        read_only_fields = ("id", "joined_at")


class ConversationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationNote
        fields = (
            "id",
            "conversation",
            "author",
            "content",
            "is_private",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
