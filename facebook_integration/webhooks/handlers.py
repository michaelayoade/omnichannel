import logging
import uuid
from typing import Dict, Optional

from django.utils import timezone

from conversations.models import Conversation
from customers.models import Customer

from ..models import (
    FacebookConversationFlow,
    FacebookMessage,
    FacebookPage,
    FacebookUser,
    FacebookUserState,
    FacebookWebhookEvent,
)
from ..services.facebook_api import FacebookMessengerService

logger = logging.getLogger(__name__)


class FacebookWebhookHandler:
    """Main webhook handler for Facebook Messenger events."""

    def __init__(self, page: FacebookPage):
        self.page = page
        self.messenger_service = FacebookMessengerService(page)

    def process_webhook_event(self, event_data: Dict) -> bool:
        """Process a webhook event from Facebook."""

        # Extract event information
        messaging_events = event_data.get("entry", [])

        for entry in messaging_events:
            page_id = entry.get("id")

            # Verify this event is for our page
            if page_id != self.page.page_id:
                continue

            # Process each messaging event
            messaging = entry.get("messaging", [])
            for event in messaging:
                try:
                    self._process_individual_event(event)
                except Exception as e:
                    logger.error(f"Error processing Facebook event: {e}")
                    continue

        return True

    def _process_individual_event(self, event: Dict):
        """Process an individual messaging event."""

        # Generate unique event ID
        event_id = str(uuid.uuid4())

        # Determine event type
        event_type = self._determine_event_type(event)

        # Create webhook event record
        webhook_event = FacebookWebhookEvent.objects.create(
            event_id=event_id, event_type=event_type, page=self.page, raw_data=event
        )

        try:
            # Get or create user
            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                webhook_event.mark_as_failed("No sender ID in event")
                return

            facebook_user = self._get_or_create_user(sender_id)
            webhook_event.facebook_user = facebook_user
            webhook_event.save()

            # Route to appropriate handler
            if event_type == "message":
                self._handle_message_event(event, facebook_user, webhook_event)
            elif event_type == "messaging_postbacks":
                self._handle_postback_event(event, facebook_user, webhook_event)
            elif event_type == "messaging_optins":
                self._handle_optin_event(event, facebook_user, webhook_event)
            elif event_type == "messaging_referrals":
                self._handle_referral_event(event, facebook_user, webhook_event)
            elif event_type == "messaging_handovers":
                self._handle_handover_event(event, facebook_user, webhook_event)
            elif event_type == "message_deliveries":
                self._handle_delivery_event(event, facebook_user, webhook_event)
            elif event_type == "message_reads":
                self._handle_read_event(event, facebook_user, webhook_event)
            else:
                webhook_event.mark_as_processed(
                    {
                        "action": "ignored",
                        "reason": f"Unhandled event type: {event_type}",
                    }
                )

        except Exception as e:
            webhook_event.mark_as_failed(str(e))
            logger.error(f"Error handling Facebook event {event_id}: {e}")

    def _determine_event_type(self, event: Dict) -> str:
        """Determine the type of webhook event."""

        if "message" in event:
            return "message"
        elif "postback" in event:
            return "messaging_postbacks"
        elif "optin" in event:
            return "messaging_optins"
        elif "referral" in event:
            return "messaging_referrals"
        elif (
            "pass_thread_control" in event
            or "take_thread_control" in event
            or "request_thread_control" in event
        ):
            return "messaging_handovers"
        elif "delivery" in event:
            return "message_deliveries"
        elif "read" in event:
            return "message_reads"
        else:
            return "unknown"

    def _get_or_create_user(self, sender_id: str) -> FacebookUser:
        """Get or create Facebook user."""

        facebook_user, created = FacebookUser.objects.get_or_create(
            psid=sender_id,
            page=self.page,
            defaults={"last_interaction_at": timezone.now()},
        )

        if created:
            # Fetch user profile from Facebook
            self._update_user_profile(facebook_user)
        else:
            facebook_user.update_last_interaction()

        return facebook_user

    def _update_user_profile(self, facebook_user: FacebookUser):
        """Update user profile from Facebook API."""

        success, profile_data = self.messenger_service.api.get_user_profile(
            facebook_user.psid
        )

        if success:
            facebook_user.first_name = profile_data.get("first_name", "")
            facebook_user.last_name = profile_data.get("last_name", "")
            facebook_user.profile_pic = profile_data.get("profile_pic", "")
            facebook_user.locale = profile_data.get("locale", "")
            facebook_user.timezone = profile_data.get("timezone")
            facebook_user.gender = profile_data.get("gender", "")
            facebook_user.save()

            # Try to match with existing customer
            self._match_customer(facebook_user)

    def _match_customer(self, facebook_user: FacebookUser):
        """Try to match Facebook user with existing customer."""

        if facebook_user.customer:
            return  # Already matched

        full_name = facebook_user.full_name.strip()
        if not full_name:
            return

        # Simple name matching - could be enhanced
        potential_customers = Customer.objects.filter(full_name__icontains=full_name)

        if potential_customers.count() == 1:
            facebook_user.customer = potential_customers.first()
            facebook_user.save(update_fields=["customer"])

    def _handle_message_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle incoming message events."""

        message_data = event.get("message", {})

        # Skip messages without mid (like delivery confirmations)
        if "mid" not in message_data:
            webhook_event.mark_as_processed(
                {"action": "ignored", "reason": "No message ID"}
            )
            return

        # Create message record
        facebook_message = self._create_message_from_event(message_data, facebook_user)
        webhook_event.facebook_message = facebook_message
        webhook_event.save()

        # Update statistics
        self.page.total_messages_received += 1
        self.page.save(update_fields=["total_messages_received"])

        facebook_user.total_messages_received += 1
        facebook_user.save(update_fields=["total_messages_received"])

        # Create or get conversation
        conversation = self._get_or_create_conversation(facebook_user)
        facebook_message.conversation = conversation
        facebook_message.save()

        # Process conversation flows
        self._process_conversation_flows(facebook_user, facebook_message)

        webhook_event.mark_as_processed(
            {
                "message_id": facebook_message.message_id,
                "conversation_id": conversation.id if conversation else None,
            }
        )

    def _create_message_from_event(
        self, message_data: Dict, facebook_user: FacebookUser
    ) -> FacebookMessage:
        """Create FacebookMessage from webhook event data."""

        mid = message_data.get("mid")
        timestamp = message_data.get("timestamp")

        # Determine message type and content
        message_type = "text"
        text_content = ""
        attachment_url = ""
        attachment_type = ""
        attachment_payload = {}
        quick_reply_payload = ""

        # Handle text messages
        if "text" in message_data:
            text_content = message_data["text"]

        # Handle quick replies
        if "quick_reply" in message_data:
            message_type = "quick_reply"
            quick_reply_payload = message_data["quick_reply"].get("payload", "")

        # Handle attachments
        if "attachments" in message_data:
            attachments = message_data["attachments"]
            if attachments:
                attachment = attachments[0]  # Take first attachment
                attachment_type = attachment.get("type", "")
                message_type = attachment_type

                payload = attachment.get("payload", {})
                attachment_payload = payload
                attachment_url = payload.get("url", "")

        # Handle stickers
        if "sticker_id" in message_data:
            message_type = "sticker"
            attachment_payload = {"sticker_id": message_data["sticker_id"]}

        return FacebookMessage.objects.create(
            message_id=mid,
            facebook_message_id=mid,
            page=self.page,
            facebook_user=facebook_user,
            message_type=message_type,
            direction="inbound",
            status="received",
            text=text_content,
            payload=message_data,
            quick_reply_payload=quick_reply_payload,
            attachment_url=attachment_url,
            attachment_type=attachment_type,
            attachment_payload=attachment_payload,
            created_at=(
                timezone.datetime.fromtimestamp(
                    timestamp / 1000, tz=timezone.get_current_timezone()
                )
                if timestamp
                else timezone.now()
            ),
        )

    def _handle_postback_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle postback events (button clicks)."""

        postback_data = event.get("postback", {})
        payload = postback_data.get("payload", "")
        title = postback_data.get("title", "")

        # Create message record for postback
        facebook_message = FacebookMessage.objects.create(
            message_id=f"postback_{int(timezone.now().timestamp() * 1000)}_{facebook_user.psid}",
            page=self.page,
            facebook_user=facebook_user,
            message_type="postback",
            direction="inbound",
            status="received",
            text=title,
            payload={"postback_payload": payload, "title": title},
            quick_reply_payload=payload,
        )

        webhook_event.facebook_message = facebook_message
        webhook_event.save()

        # Get conversation
        conversation = self._get_or_create_conversation(facebook_user)
        facebook_message.conversation = conversation
        facebook_message.save()

        # Process postback through conversation flows
        self._process_postback_flows(facebook_user, payload, facebook_message)

        webhook_event.mark_as_processed(
            {
                "payload": payload,
                "title": title,
                "message_id": facebook_message.message_id,
            }
        )

    def _handle_optin_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle opt-in events."""

        optin_data = event.get("optin", {})
        ref = optin_data.get("ref", "")

        # Update user subscription status
        facebook_user.is_subscribed = True
        facebook_user.save(update_fields=["is_subscribed"])

        webhook_event.mark_as_processed({"action": "user_opted_in", "ref": ref})

        # Trigger welcome flow if enabled
        if self.page.welcome_message_enabled:
            self._trigger_welcome_flow(facebook_user)

    def _handle_referral_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle referral events."""

        referral_data = event.get("referral", {})
        ref = referral_data.get("ref", "")
        source = referral_data.get("source", "")
        type_referral = referral_data.get("type", "")

        webhook_event.mark_as_processed(
            {
                "action": "referral_received",
                "ref": ref,
                "source": source,
                "type": type_referral,
            }
        )

        # Process referral flows
        self._process_referral_flows(facebook_user, ref)

    def _handle_handover_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle handover protocol events."""

        if "pass_thread_control" in event:
            self._handle_thread_control_passed(event, facebook_user, webhook_event)
        elif "take_thread_control" in event:
            self._handle_thread_control_taken(event, facebook_user, webhook_event)
        elif "request_thread_control" in event:
            self._handle_thread_control_requested(event, facebook_user, webhook_event)

    def _handle_thread_control_passed(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle thread control passed to another app."""

        pass_data = event.get("pass_thread_control", {})
        new_owner_app_id = pass_data.get("new_owner_app_id", "")
        metadata = pass_data.get("metadata", "")

        # Update user state
        user_state, _ = FacebookUserState.objects.get_or_create(
            facebook_user=facebook_user
        )
        user_state.in_handover = True
        user_state.handover_app_id = new_owner_app_id
        user_state.handover_metadata = {"metadata": metadata}
        user_state.save()

        webhook_event.mark_as_processed(
            {
                "action": "thread_control_passed",
                "new_owner_app_id": new_owner_app_id,
                "metadata": metadata,
            }
        )

    def _handle_thread_control_taken(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle thread control taken by our app."""

        take_data = event.get("take_thread_control", {})
        previous_owner_app_id = take_data.get("previous_owner_app_id", "")
        metadata = take_data.get("metadata", "")

        # Update user state
        user_state, _ = FacebookUserState.objects.get_or_create(
            facebook_user=facebook_user
        )
        user_state.in_handover = False
        user_state.handover_app_id = ""
        user_state.handover_metadata = {}
        user_state.save()

        webhook_event.mark_as_processed(
            {
                "action": "thread_control_taken",
                "previous_owner_app_id": previous_owner_app_id,
                "metadata": metadata,
            }
        )

    def _handle_thread_control_requested(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle thread control request."""

        request_data = event.get("request_thread_control", {})
        requested_owner_app_id = request_data.get("requested_owner_app_id", "")
        metadata = request_data.get("metadata", "")

        webhook_event.mark_as_processed(
            {
                "action": "thread_control_requested",
                "requested_owner_app_id": requested_owner_app_id,
                "metadata": metadata,
            }
        )

        # Could implement automatic approval logic here

    def _handle_delivery_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle message delivery events."""

        delivery_data = event.get("delivery", {})
        mids = delivery_data.get("mids", [])
        watermark = delivery_data.get("watermark")

        # Update message delivery status
        updated_count = 0
        for mid in mids:
            try:
                message = FacebookMessage.objects.get(
                    facebook_message_id=mid, page=self.page
                )
                message.mark_as_delivered()
                updated_count += 1
            except FacebookMessage.DoesNotExist:
                continue

        webhook_event.mark_as_processed(
            {
                "action": "delivery_update",
                "updated_messages": updated_count,
                "watermark": watermark,
            }
        )

    def _handle_read_event(
        self,
        event: Dict,
        facebook_user: FacebookUser,
        webhook_event: FacebookWebhookEvent,
    ):
        """Handle message read events."""

        read_data = event.get("read", {})
        watermark = read_data.get("watermark")

        # Update read status for messages before watermark
        updated_count = FacebookMessage.objects.filter(
            page=self.page,
            facebook_user=facebook_user,
            direction="outbound",
            created_at__lte=timezone.datetime.fromtimestamp(
                watermark / 1000, tz=timezone.get_current_timezone()
            ),
        ).update(status="read", read_at=timezone.now())

        webhook_event.mark_as_processed(
            {
                "action": "read_update",
                "updated_messages": updated_count,
                "watermark": watermark,
            }
        )

    def _get_or_create_conversation(
        self, facebook_user: FacebookUser
    ) -> Optional[Conversation]:
        """Get or create conversation for Facebook user."""

        # Try to get existing active conversation
        existing_conversation = Conversation.objects.filter(
            facebook_messages__facebook_user=facebook_user,
            status__in=["open", "pending"],
        ).first()

        if existing_conversation:
            return existing_conversation

        # Create new conversation
        try:
            conversation = Conversation.objects.create(
                customer=facebook_user.customer,
                channel="facebook",
                status="open",
                subject=f"Facebook conversation with {facebook_user.display_name}",
                metadata={
                    "facebook_user_psid": facebook_user.psid,
                    "facebook_page_id": self.page.page_id,
                },
            )

            # Update page conversation count
            self.page.total_conversations += 1
            self.page.save(update_fields=["total_conversations"])

            return conversation

        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            return None

    def _process_conversation_flows(
        self, facebook_user: FacebookUser, facebook_message: FacebookMessage
    ):
        """Process conversation flows for incoming messages."""

        # Get user state
        user_state, _ = FacebookUserState.objects.get_or_create(
            facebook_user=facebook_user
        )

        # Skip if in handover
        if user_state.in_handover:
            return

        # If user is in a flow, continue it
        if user_state.current_flow:
            self._continue_conversation_flow(user_state, facebook_message)
        else:
            # Check for new flow triggers
            self._check_flow_triggers(facebook_user, facebook_message)

    def _process_postback_flows(
        self,
        facebook_user: FacebookUser,
        payload: str,
        facebook_message: FacebookMessage,
    ):
        """Process conversation flows for postback events."""

        # Get user state
        user_state, _ = FacebookUserState.objects.get_or_create(
            facebook_user=facebook_user
        )

        # Skip if in handover
        if user_state.in_handover:
            return

        # Handle Get Started button
        if payload == "GET_STARTED":
            self._trigger_welcome_flow(facebook_user)
            return

        # If user is in a flow, process postback within flow
        if user_state.current_flow:
            self._continue_conversation_flow(user_state, facebook_message)
        else:
            # Check for flows triggered by postback
            flows = FacebookConversationFlow.objects.filter(
                page=self.page,
                trigger_type="postback",
                trigger_value=payload,
                is_active=True,
            ).order_by("-priority")

            if flows.exists():
                self._start_conversation_flow(user_state, flows.first())

    def _process_referral_flows(self, facebook_user: FacebookUser, ref: str):
        """Process conversation flows for referral events."""

        flows = FacebookConversationFlow.objects.filter(
            page=self.page, trigger_type="referral", trigger_value=ref, is_active=True
        ).order_by("-priority")

        if flows.exists():
            user_state, _ = FacebookUserState.objects.get_or_create(
                facebook_user=facebook_user
            )
            self._start_conversation_flow(user_state, flows.first())

    def _check_flow_triggers(
        self, facebook_user: FacebookUser, facebook_message: FacebookMessage
    ):
        """Check for conversation flow triggers in incoming message."""

        message_text = facebook_message.text.lower().strip()

        # Check for keyword triggers
        keyword_flows = FacebookConversationFlow.objects.filter(
            page=self.page, trigger_type="keyword", is_active=True
        ).order_by("-priority")

        for flow in keyword_flows:
            keywords = flow.trigger_value.lower().split(",")
            for keyword in keywords:
                keyword = keyword.strip()
                if keyword and keyword in message_text:
                    user_state, _ = FacebookUserState.objects.get_or_create(
                        facebook_user=facebook_user
                    )
                    self._start_conversation_flow(user_state, flow)
                    return

    def _trigger_welcome_flow(self, facebook_user: FacebookUser):
        """Trigger welcome flow for new users."""

        welcome_flows = FacebookConversationFlow.objects.filter(
            page=self.page, flow_type="welcome", is_active=True
        ).order_by("-priority")

        if welcome_flows.exists():
            user_state, _ = FacebookUserState.objects.get_or_create(
                facebook_user=facebook_user
            )
            self._start_conversation_flow(user_state, welcome_flows.first())

    def _start_conversation_flow(
        self, user_state: FacebookUserState, flow: FacebookConversationFlow
    ):
        """Start a conversation flow for a user."""

        flow.increment_usage()

        user_state.update_state(
            flow=flow,
            step="start",
            data={"flow_started_at": timezone.now().isoformat()},
        )

        # Execute first step of flow
        self._execute_flow_step(user_state, "start")

    def _continue_conversation_flow(
        self, user_state: FacebookUserState, facebook_message: FacebookMessage
    ):
        """Continue an existing conversation flow."""

        # This would contain the flow execution logic
        # For now, we'll just log that a flow is continuing
        logger.info(
            f"Continuing flow {user_state.current_flow.name} for user {user_state.facebook_user.psid}"
        )

        # Execute next step based on current step and user input
        self._execute_flow_step(user_state, user_state.current_step, facebook_message)

    def _execute_flow_step(
        self,
        user_state: FacebookUserState,
        step: str,
        facebook_message: FacebookMessage = None,
    ):
        """Execute a specific step in a conversation flow."""

        flow = user_state.current_flow
        if not flow:
            return

        flow_steps = flow.flow_steps

        # Get step configuration
        step_config = flow_steps.get(step, {})

        if not step_config:
            logger.warning(f"Step {step} not found in flow {flow.name}")
            return

        # Execute step actions
        actions = step_config.get("actions", [])

        for action in actions:
            self._execute_flow_action(user_state, action, facebook_message)

        # Determine next step
        next_step = self._determine_next_step(user_state, step_config, facebook_message)

        if next_step:
            user_state.update_state(step=next_step)
        else:
            # Flow completed
            flow.increment_completion()
            user_state.reset_state()

    def _execute_flow_action(
        self,
        user_state: FacebookUserState,
        action: Dict,
        facebook_message: FacebookMessage = None,
    ):
        """Execute a flow action."""

        action_type = action.get("type")
        facebook_user = user_state.facebook_user

        if action_type == "send_text":
            text = action.get("text", "")
            # Process variables in text
            text = self._process_flow_variables(text, user_state, facebook_message)
            self.messenger_service.send_text(facebook_user.psid, text)

        elif action_type == "send_quick_replies":
            text = action.get("text", "")
            quick_replies = action.get("quick_replies", [])
            text = self._process_flow_variables(text, user_state, facebook_message)
            self.messenger_service.send_quick_reply(
                facebook_user.psid, text, quick_replies
            )

        elif action_type == "send_template":
            template_id = action.get("template_id")
            variables = action.get("variables", {})
            # Process variables
            processed_variables = self._process_flow_variables(
                variables, user_state, facebook_message
            )

            try:
                from ..models import FacebookTemplate

                template = FacebookTemplate.objects.get(id=template_id)
                self.messenger_service.send_template_message(
                    facebook_user.psid, template, processed_variables
                )
            except FacebookTemplate.DoesNotExist:
                logger.error(f"Template {template_id} not found")

        elif action_type == "set_variable":
            variable_name = action.get("name")
            variable_value = action.get("value")
            if variable_name:
                user_state.context_variables[variable_name] = variable_value
                user_state.save()

        elif action_type == "delay":
            # Could implement delays for more natural conversation flow
            pass

    def _determine_next_step(
        self,
        user_state: FacebookUserState,
        step_config: Dict,
        facebook_message: FacebookMessage = None,
    ) -> Optional[str]:
        """Determine the next step in a conversation flow."""

        next_steps = step_config.get("next", {})

        if isinstance(next_steps, str):
            return next_steps

        if isinstance(next_steps, dict):
            # Conditional next steps
            for condition, next_step in next_steps.items():
                if self._evaluate_flow_condition(
                    condition, user_state, facebook_message
                ):
                    return next_step

        return step_config.get("default_next")

    def _evaluate_flow_condition(
        self,
        condition: str,
        user_state: FacebookUserState,
        facebook_message: FacebookMessage = None,
    ) -> bool:
        """Evaluate a flow condition."""

        # Simple condition evaluation - could be enhanced
        if not facebook_message:
            return False

        if condition.startswith("text_contains:"):
            text_to_check = condition.split(":", 1)[1].lower()
            return text_to_check in facebook_message.text.lower()

        elif condition.startswith("quick_reply_payload:"):
            payload_to_check = condition.split(":", 1)[1]
            return facebook_message.quick_reply_payload == payload_to_check

        elif condition == "has_attachment":
            return facebook_message.has_attachment

        return False

    def _process_flow_variables(
        self,
        content,
        user_state: FacebookUserState,
        facebook_message: FacebookMessage = None,
    ):
        """Process variables in flow content."""

        if isinstance(content, str):
            # Replace user variables
            facebook_user = user_state.facebook_user
            content = content.replace("{{first_name}}", facebook_user.first_name)
            content = content.replace("{{last_name}}", facebook_user.last_name)
            content = content.replace("{{full_name}}", facebook_user.display_name)

            # Replace context variables
            for var_name, var_value in user_state.context_variables.items():
                content = content.replace(f"{{{{{var_name}}}}}", str(var_value))

            return content

        elif isinstance(content, dict):
            # Recursively process dict values
            processed = {}
            for key, value in content.items():
                processed[key] = self._process_flow_variables(
                    value, user_state, facebook_message
                )
            return processed

        elif isinstance(content, list):
            # Process list items
            return [
                self._process_flow_variables(item, user_state, facebook_message)
                for item in content
            ]

        return content
