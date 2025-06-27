import logging

from django.db.models import Q
from django.utils import timezone

from conversations.models import Conversation, Message
from customers.models import Customer

from ..models import InstagramUser

logger = logging.getLogger(__name__)


class CustomerMatcher:
    """Service for matching Instagram users with existing customers."""

    def __init__(self):
        self.matching_strategies = [
            self._match_by_existing_instagram_profile,
            self._match_by_phone_number,
            self._match_by_email,
            self._match_by_name_similarity,
            self._match_by_conversation_history,
        ]

    def find_or_create_customer(self, instagram_user: InstagramUser) -> Customer:
        """Find existing customer or create new one for Instagram user."""
        # Try matching strategies in order of confidence
        for strategy in self.matching_strategies:
            customer = strategy(instagram_user)
            if customer:
                # Link Instagram profile to customer if not already linked
                if instagram_user.customer != customer:
                    self._link_instagram_to_customer(instagram_user, customer)
                return customer

        # No match found, create new customer
        return self._create_new_customer(instagram_user)

    def _match_by_existing_instagram_profile(
        self, instagram_user: InstagramUser,
    ) -> Customer | None:
        """Check if Instagram user is already linked to a customer."""
        if instagram_user.customer:
            logger.info(
                f"Instagram user {instagram_user.display_name} already linked to customer {instagram_user.customer.id}",
            )
            return instagram_user.customer
        return None

    def _match_by_phone_number(
        self, instagram_user: InstagramUser,
    ) -> Customer | None:
        """Match by phone number if available in Instagram profile."""
        # Instagram API doesn't typically provide phone numbers
        # This is a placeholder for future enhancement or manual entry
        return None

    def _match_by_email(self, instagram_user: InstagramUser) -> Customer | None:
        """Match by email if available in Instagram profile."""
        # Instagram API doesn't typically provide email addresses
        # This is a placeholder for future enhancement or manual entry
        return None

    def _match_by_name_similarity(
        self, instagram_user: InstagramUser,
    ) -> Customer | None:
        """Match by name similarity with existing customers."""
        if not instagram_user.name:
            return None

        # Split name into parts for matching
        name_parts = instagram_user.name.lower().split()
        if not name_parts:
            return None

        # Search for customers with similar names
        query = Q()
        for part in name_parts:
            if len(part) > 2:  # Only match meaningful name parts
                query |= Q(first_name__icontains=part) | Q(last_name__icontains=part)

        if query:
            customers = Customer.objects.filter(query)[:5]  # Limit to top 5 matches

            # Simple scoring based on name overlap
            best_match = None
            best_score = 0

            for customer in customers:
                score = self._calculate_name_similarity_score(
                    instagram_user.name,
                    f"{customer.first_name} {customer.last_name}".strip(),
                )
                if score > best_score and score > 0.7:  # Threshold for matching
                    best_score = score
                    best_match = customer

            if best_match:
                logger.info(
                    f"Matched Instagram user {instagram_user.display_name} to customer {best_match.id} by name similarity (score: {best_score})",
                )
                return best_match

        return None

    def _match_by_conversation_history(
        self, instagram_user: InstagramUser,
    ) -> Customer | None:
        """Match by previous conversation history across channels."""
        # Look for conversations with similar user identifiers
        # This is more complex and might involve cross-channel matching
        return None

    def _calculate_name_similarity_score(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two names."""
        if not name1 or not name2:
            return 0.0

        name1_parts = set(name1.lower().split())
        name2_parts = set(name2.lower().split())

        if not name1_parts or not name2_parts:
            return 0.0

        # Calculate Jaccard similarity
        intersection = name1_parts.intersection(name2_parts)
        union = name1_parts.union(name2_parts)

        return len(intersection) / len(union) if union else 0.0

    def _link_instagram_to_customer(
        self, instagram_user: InstagramUser, customer: Customer,
    ):
        """Link Instagram user to customer."""
        instagram_user.customer = customer
        instagram_user.save(update_fields=["customer"])
        logger.info(
            f"Linked Instagram user {instagram_user.display_name} to customer {customer.id}",
        )

    def _create_new_customer(self, instagram_user: InstagramUser) -> Customer:
        """Create new customer for Instagram user."""
        # Extract name parts
        first_name = ""
        last_name = ""

        if instagram_user.name:
            name_parts = instagram_user.name.split()
            if len(name_parts) == 1:
                first_name = name_parts[0]
            elif len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])

        # Use username as fallback
        if not first_name and instagram_user.username:
            first_name = instagram_user.username

        # Create customer
        customer = Customer.objects.create(
            first_name=first_name
            or f"Instagram User {instagram_user.instagram_user_id[:8]}",
            last_name=last_name,
            source="instagram",
            created_via="instagram_dm",
        )

        # Link Instagram profile
        self._link_instagram_to_customer(instagram_user, customer)

        logger.info(
            f"Created new customer {customer.id} for Instagram user {instagram_user.display_name}",
        )
        return customer


class ConversationManager:
    """Manage conversations for Instagram messages."""

    def __init__(self):
        self.customer_matcher = CustomerMatcher()

    def get_or_create_conversation(self, instagram_user: InstagramUser) -> Conversation:
        """Get or create conversation for Instagram user."""
        # Find or create customer
        customer = self.customer_matcher.find_or_create_customer(instagram_user)

        # Look for existing Instagram conversation
        existing_conversation = Conversation.objects.filter(
            customer=customer, channel="instagram", status__in=["open", "pending"],
        ).first()

        if existing_conversation:
            # Update last activity
            existing_conversation.last_message_at = timezone.now()
            existing_conversation.save(update_fields=["last_message_at"])
            return existing_conversation

        # Create new conversation
        conversation = Conversation.objects.create(
            customer=customer,
            channel="instagram",
            status="open",
            subject=f"Instagram DM - {instagram_user.display_name}",
            created_by_customer=True,
            last_message_at=timezone.now(),
        )

        logger.info(
            f"Created conversation {conversation.id} for Instagram user {instagram_user.display_name}",
        )
        return conversation

    def create_conversation_message(
        self, instagram_message, conversation: Conversation,
    ) -> Message:
        """Create conversation message from Instagram message."""
        # Determine message content
        content = instagram_message.text
        if instagram_message.has_media:
            if content:
                content += f"\n[Media: {instagram_message.media_url}]"
            else:
                content = f"[Media: {instagram_message.media_url}]"

        # Create message
        message = Message.objects.create(
            conversation=conversation,
            content=content,
            sender_type=(
                "customer" if instagram_message.direction == "inbound" else "agent"
            ),
            channel="instagram",
            external_id=instagram_message.message_id,
            created_at=instagram_message.timestamp,
        )

        # Update conversation
        conversation.last_message_at = instagram_message.timestamp
        conversation.message_count += 1
        if instagram_message.direction == "inbound":
            conversation.status = "open"
        conversation.save()

        logger.info(
            f"Created conversation message {message.id} for Instagram message {instagram_message.message_id}",
        )
        return message

    def sync_instagram_message_to_conversation(self, instagram_message):
        """Sync Instagram message to conversation system."""
        # Get or create conversation
        conversation = self.get_or_create_conversation(instagram_message.instagram_user)

        # Link Instagram message to conversation
        instagram_message.conversation = conversation
        instagram_message.save(update_fields=["conversation"])

        # Create conversation message
        message = self.create_conversation_message(instagram_message, conversation)

        return conversation, message


class InstagramUserService:
    """Service for Instagram user operations."""

    def __init__(self):
        self.customer_matcher = CustomerMatcher()
        self.conversation_manager = ConversationManager()

    def enrich_user_profile(self, instagram_user: InstagramUser) -> InstagramUser:
        """Enrich Instagram user profile with customer data."""
        # Find or create customer
        customer = self.customer_matcher.find_or_create_customer(instagram_user)

        # Update user with customer information if available
        if customer and not instagram_user.name and customer.full_name:
            instagram_user.name = customer.full_name
            instagram_user.save(update_fields=["name"])

        return instagram_user

    def get_user_conversation_history(
        self, instagram_user: InstagramUser,
    ) -> list[dict]:
        """Get conversation history for Instagram user across all channels."""
        if not instagram_user.customer:
            return []

        conversations = Conversation.objects.filter(
            customer=instagram_user.customer,
        ).order_by("-last_message_at")[:10]

        history = []
        for conversation in conversations:
            history.append(
                {
                    "id": conversation.id,
                    "channel": conversation.channel,
                    "subject": conversation.subject,
                    "status": conversation.status,
                    "message_count": conversation.message_count,
                    "last_message_at": conversation.last_message_at,
                    "created_at": conversation.created_at,
                },
            )

        return history

    def identify_user_intent(self, instagram_message) -> dict:
        """Analyze message to identify user intent."""
        # Simple intent analysis - can be enhanced with NLP
        content = instagram_message.text.lower() if instagram_message.text else ""

        intents = {
            "support": ["help", "problem", "issue", "support", "broken"],
            "sales": ["buy", "purchase", "price", "cost", "order", "product"],
            "information": ["info", "about", "how", "what", "when", "where"],
            "greeting": ["hi", "hello", "hey", "good morning", "good afternoon"],
        }

        detected_intents = []
        for intent, keywords in intents.items():
            if any(keyword in content for keyword in keywords):
                detected_intents.append(intent)

        return {
            "detected_intents": detected_intents,
            "primary_intent": detected_intents[0] if detected_intents else "general",
            "confidence": 0.8 if detected_intents else 0.3,
        }
