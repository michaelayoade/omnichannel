import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation_group_name = f"conversation_{self.conversation_id}"

        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name, self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave conversation group
        await self.channel_layer.group_discard(
            self.conversation_group_name, self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Send message to conversation group
        await self.channel_layer.group_send(
            self.conversation_group_name, {"type": "chat_message", "message": message}
        )

    # Receive message from conversation group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))


class AgentStatusConsumer(AsyncWebsocketConsumer):
    """
    Handles WebSocket connections for real-time agent status updates.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if (
            not self.user
            or not self.user.is_authenticated
            or not hasattr(self.user, "agent_profile")
        ):
            await self.close()
            return

        self.agent_id = self.user.id
        self.group_name = "agent_status"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(
            self.group_name,
            {"type": "agent_update", "agent_id": self.agent_id, "status": "online"},
        )

    async def disconnect(self, close_code):
        if (
            not self.user
            or not self.user.is_authenticated
            or not hasattr(self.user, "agent_profile")
        ):
            return

        await self.channel_layer.group_send(
            self.group_name,
            {"type": "agent_update", "agent_id": self.agent_id, "status": "offline"},
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Receives status updates from the agent.
        e.g., {'status': 'away'}
        """
        data = json.loads(text_data)
        status = data.get("status")
        if status in ["online", "away", "busy"]:
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "agent_update", "agent_id": self.agent_id, "status": status},
            )

    async def agent_update(self, event):
        """
        Sends agent status updates to the WebSocket.
        """
        await self.send(
            text_data=json.dumps(
                {"agent_id": event["agent_id"], "status": event["status"]}
            )
        )


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Handles WebSocket connections for sending notifications to agents.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if (
            not self.user
            or not self.user.is_authenticated
            or not hasattr(self.user, "agent_profile")
        ):
            await self.close()
            return

        self.group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if (
            not self.user
            or not self.user.is_authenticated
            or not hasattr(self.user, "agent_profile")
        ):
            return

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
        """
        Sends a notification to the agent.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": event.get("notification_type"),
                    "payload": event.get("payload"),
                }
            )
        )
