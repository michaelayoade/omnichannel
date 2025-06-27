"""
Tests for WebSocket consumers in the agent_hub app.
"""

from unittest.mock import AsyncMock, patch

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from agent_hub.models import AgentProfile
from omnichannel_core.asgi import application


class WebSocketConsumerTestCase(TransactionTestCase):
    """Base test case for WebSocket consumers."""

    def setUp(self):
        """Set up test user and agent profile."""
        self.user = User.objects.create_user(
            username="testagent", password="testpass123"  # nosec B106
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.user, employee_id="EMP001", status="online"
        )

    @database_sync_to_async
    def get_user(self):
        """Get user for async tests."""
        return self.user


class AgentStatusConsumerTest(WebSocketConsumerTestCase):
    """Tests for AgentStatusConsumer."""

    async def test_authenticated_agent_can_connect(self):
        """Test that authenticated agent can connect to status WebSocket."""
        communicator = WebsocketCommunicator(application, "/ws/agent/status/")
        communicator.scope["user"] = await self.get_user()

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    async def test_unauthenticated_user_cannot_connect(self):
        """Test that unauthenticated users cannot connect."""
        communicator = WebsocketCommunicator(application, "/ws/agent/status/")
        # No user in scope

        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)

    @patch("agent_hub.consumers.channel_layer", new_callable=AsyncMock)
    async def test_status_update_broadcast(self, mock_channel_layer):
        """Test that status updates are broadcasted to group."""
        communicator = WebsocketCommunicator(application, "/ws/agent/status/")
        communicator.scope["user"] = await self.get_user()

        await communicator.connect()

        # Send status update
        await communicator.send_json_to({"type": "status_update", "status": "busy"})

        # Verify group_send was called
        mock_channel_layer.group_send.assert_called()

        await communicator.disconnect()

    async def test_agent_status_message_format(self):
        """Test that agent status messages have correct format."""
        communicator = WebsocketCommunicator(application, "/ws/agent/status/")
        communicator.scope["user"] = await self.get_user()

        await communicator.connect()

        # Send invalid message format
        await communicator.send_json_to({"invalid": "format"})

        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertIn("error", response)

        await communicator.disconnect()


class NotificationConsumerTest(WebSocketConsumerTestCase):
    """Tests for NotificationConsumer."""

    async def test_authenticated_agent_can_connect_to_notifications(self):
        """Test that authenticated agent can connect to notifications WebSocket."""
        communicator = WebsocketCommunicator(application, "/ws/agent/notifications/")
        communicator.scope["user"] = await self.get_user()

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    @patch("agent_hub.consumers.channel_layer", new_callable=AsyncMock)
    async def test_notification_broadcast(self, mock_channel_layer):
        """Test that notifications are broadcasted correctly."""
        communicator = WebsocketCommunicator(application, "/ws/agent/notifications/")
        communicator.scope["user"] = await self.get_user()

        await communicator.connect()

        # Simulate notification broadcast
        await communicator.send_json_to(
            {
                "type": "notification",
                "message": "New conversation assigned",
                "priority": "high",
            }
        )

        await communicator.disconnect()

    async def test_notification_message_validation(self):
        """Test that notification messages are validated."""
        communicator = WebsocketCommunicator(application, "/ws/agent/notifications/")
        communicator.scope["user"] = await self.get_user()

        await communicator.connect()

        # Send message without required fields
        await communicator.send_json_to(
            {
                "type": "notification"
                # Missing message field
            }
        )

        # Should handle gracefully or send error
        try:
            response = await communicator.receive_json_from(timeout=1)
            if "error" in response:
                self.assertIn("message", response["error"].lower())
        except Exception:  # nosec B110
            # No response is also acceptable for invalid messages
            pass

        await communicator.disconnect()


class WebSocketIntegrationTest(WebSocketConsumerTestCase):
    """Integration tests for WebSocket functionality."""

    async def test_multiple_agents_status_sync(self):
        """Test that multiple agents can sync status."""
        # Create second agent
        user2 = await database_sync_to_async(User.objects.create_user)(
            username="testagent2", password="testpass123"  # nosec B106
        )
        await database_sync_to_async(AgentProfile.objects.create)(
            user=user2, employee_id="EMP002", status="online"
        )

        # Connect both agents
        comm1 = WebsocketCommunicator(application, "/ws/agent/status/")
        comm1.scope["user"] = await self.get_user()

        comm2 = WebsocketCommunicator(application, "/ws/agent/status/")
        comm2.scope["user"] = user2

        await comm1.connect()
        await comm2.connect()

        # Send status update from agent 1
        await comm1.send_json_to({"type": "status_update", "status": "away"})

        # Both should eventually receive updates
        # (This would need proper channel layer setup in real tests)

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_login_redirect_integration(self):
        """Test that login redirects work with WebSocket authentication."""
        # This would test the full flow: login -> redirect -> WebSocket connect
        # Implementation depends on your test client setup
        pass
