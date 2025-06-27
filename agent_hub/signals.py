from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Conversation, Message
from .serializers import MessageSerializer


@receiver(post_save, sender=Message)
def broadcast_message(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        conversation_id = str(instance.conversation.id)
        conversation_group_name = f"conversation_{conversation_id}"

        message_data = MessageSerializer(instance).data

        async_to_sync(channel_layer.group_send)(
            conversation_group_name, {"type": "chat_message", "message": message_data}
        )


@receiver(post_save, sender=Message)
def update_conversation_last_message_at(sender, instance, created, **kwargs):
    """
    Update the parent Conversation's last_message_at timestamp when a new message is created.
    """
    if created:
        conversation = instance.conversation
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=instance.sent_at
        )
