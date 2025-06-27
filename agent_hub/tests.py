from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITransactionTestCase

from . import services
from .models import (
    AgentPerformanceSnapshot,
    AgentProfile,
    Conversation,
    Message,
    QuickReplyTemplate,
)
from .tasks import update_agent_performance_snapshots

User = get_user_model()


class AgentHubAPITests(APITransactionTestCase):
    def setUp(self):
        # Ensure a clean slate for quick replies before each test
        QuickReplyTemplate.objects.all().delete()

        # Create a test user
        self.user = User.objects.create_user(
            username="testagent", password="testpassword",  # nosec B106
        )
        # Create an agent profile for the user
        self.agent_profile = AgentProfile.objects.create(user=self.user)
        # Create a quick reply template for testing
        self.quick_reply = QuickReplyTemplate.objects.create(
            agent=self.user,
            title="Greeting",
            shortcut="hello",
            content="Hello! How can I help you today?",
        )
        # Authenticate the client
        self.client.force_authenticate(user=self.user)

    def test_set_agent_status(self):
        """Ensure we can update an agent's status."""
        url = "/api/agent_hub/agent-profiles/set-status/"
        data = {"status": "busy"}
        response = self.client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "busy"

        # Refresh the profile from the database and check the status
        self.agent_profile.refresh_from_db()
        assert self.agent_profile.status == "busy"

    def test_list_quick_replies(self):
        """Ensure we can list quick reply templates."""
        url = "/api/agent_hub/quick-replies/"
        response = self.client.get(url, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["shortcut"] == "hello"

    def test_unauthenticated_access(self):
        """Ensure unauthenticated users cannot access the endpoints."""
        # De-authenticate the client
        self.client.force_authenticate(user=None)

        # Test agent status endpoint
        status_url = "/api/agent_hub/agent-profiles/set-status/"
        status_response = self.client.post(
            status_url, {"status": "offline"}, format="json",
        )
        assert status_response.status_code == status.HTTP_403_FORBIDDEN

        # Test quick replies endpoint
        qr_url = "/api/agent_hub/quick-replies/"
        qr_response = self.client.get(qr_url, format="json")
        assert qr_response.status_code == status.HTTP_403_FORBIDDEN


class AgentPerformanceSnapshotTaskTests(APITransactionTestCase):
    def setUp(self):
        # Create a test user and agent profile
        self.user = User.objects.create_user(
            username="perftestagent", password="testpassword",  # nosec B106
        )
        self.agent_profile = AgentProfile.objects.create(user=self.user)

        # Create some test data

        # Create a customer for the conversation
        from customers.models import Customer

        self.customer = Customer.objects.create(
            customer_id="test-customer-123",
            first_name="Test",
            last_name="Customer",
            email="test@customer.com",
        )

        # Create a conversation that was closed yesterday for the task to pick up
        last_message_time = (timezone.now() - timedelta(days=1)).replace(
            hour=15, minute=0, second=0, microsecond=0,
        )
        created_time = last_message_time - timedelta(minutes=10)

        conversation = Conversation.objects.create(
            customer=self.customer,
            assigned_agent=self.user,
            status="closed",
            created_at=created_time,
            channel="email",
        )

        # Create a message for the conversation. The signal should update the
        # conversation,
        # but we will manually set it afterwards to ensure the test is isolated.
        import uuid

        Message.objects.create(
            conversation=conversation,
            direction="outbound",
            body="This is a test message from the agent.",
            channel_message_id=str(uuid.uuid4()),
            sent_at=last_message_time,
        )

        # Manually update the timestamp to guarantee the correct state for the test
        conversation.last_message_at = last_message_time
        conversation.save(update_fields=["last_message_at"])

    def test_update_agent_performance_snapshots_task(self):
        """Test that the Celery task correctly creates a performance snapshot."""
        # Run the task synchronously for testing
        update_agent_performance_snapshots()

        # Check if the snapshot was created
        assert AgentPerformanceSnapshot.objects.count() == 1

        snapshot = AgentPerformanceSnapshot.objects.first()
        assert snapshot.agent == self.agent_profile.user
        assert snapshot.conversations_closed == 1
        assert snapshot.messages_sent == 1
        assert snapshot.messages_received == 0
        assert snapshot.response_time_avg_seconds == 600


class AgentHubServiceTests(APITransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="servicetestagent", password="testpassword",  # nosec B106
        )
        self.agent_profile = AgentProfile.objects.create(user=self.user)

    def test_update_agent_status_success(self):
        """Test that the agent status can be successfully updated."""
        updated_profile = services.update_agent_status(self.agent_profile, "busy")
        assert updated_profile.status == "busy"
        self.agent_profile.refresh_from_db()
        assert self.agent_profile.status == "busy"

    def test_update_agent_status_invalid(self):
        """Test that providing an invalid status raises a ValidationError."""
        with pytest.raises(ValidationError):
            services.update_agent_status(self.agent_profile, "on_a_break")
