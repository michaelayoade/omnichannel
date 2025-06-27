import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import InstagramAccount, InstagramMessage, InstagramUser
from .services import InstagramAPIError, InstagramMessageService
from .utils import ConversationManager
from .webhooks import instagram_webhook_view

logger = logging.getLogger(__name__)


@csrf_exempt
def instagram_webhook(request: HttpRequest):
    """Handle Instagram webhook requests."""
    return instagram_webhook_view(request)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_text_message(request: HttpRequest):
    """Send a text message via Instagram DM."""
    try:
        data = json.loads(request.body)

        # Extract required fields
        account_id = data.get("account_id")
        instagram_user_id = data.get("instagram_user_id")
        text = data.get("text")

        if not all([account_id, instagram_user_id, text]):
            return JsonResponse(
                {
                    "error": "Missing required fields: account_id, instagram_user_id, text"
                },
                status=400,
            )

        # Get account and user
        account = get_object_or_404(InstagramAccount, id=account_id)
        instagram_user = get_object_or_404(
            InstagramUser, instagram_user_id=instagram_user_id, account=account
        )

        # Send message
        message_service = InstagramMessageService(account)
        message = message_service.send_text_message(instagram_user, text)

        # Sync to conversation system
        conversation_manager = ConversationManager()
        conversation, conv_message = (
            conversation_manager.sync_instagram_message_to_conversation(message)
        )

        return JsonResponse(
            {
                "success": True,
                "message_id": message.message_id,
                "instagram_message_id": message.instagram_message_id,
                "conversation_id": conversation.id,
                "status": message.status,
            }
        )

    except InstagramAPIError as e:
        logger.error(f"Instagram API error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        logger.error(f"Error sending text message: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_image_message(request: HttpRequest):
    """Send an image message via Instagram DM."""
    try:
        # Handle multipart form data
        account_id = request.POST.get("account_id")
        instagram_user_id = request.POST.get("instagram_user_id")
        image_file = request.FILES.get("image")
        image_url = request.POST.get("image_url")

        if not all([account_id, instagram_user_id]):
            return JsonResponse(
                {"error": "Missing required fields: account_id, instagram_user_id"},
                status=400,
            )

        if not image_file and not image_url:
            return JsonResponse(
                {"error": "Either image file or image_url is required"}, status=400
            )

        # Get account and user
        account = get_object_or_404(InstagramAccount, id=account_id)
        instagram_user = get_object_or_404(
            InstagramUser, instagram_user_id=instagram_user_id, account=account
        )

        # Handle image upload if file provided
        if image_file:
            # Save file to storage
            file_name = f"instagram_images/{account.id}/{image_file.name}"
            file_path = default_storage.save(file_name, ContentFile(image_file.read()))
            image_url = default_storage.url(file_path)

        # Send image
        message_service = InstagramMessageService(account)
        message = message_service.send_image_message(instagram_user, image_url)

        # Sync to conversation system
        conversation_manager = ConversationManager()
        conversation, conv_message = (
            conversation_manager.sync_instagram_message_to_conversation(message)
        )

        return JsonResponse(
            {
                "success": True,
                "message_id": message.message_id,
                "instagram_message_id": message.instagram_message_id,
                "conversation_id": conversation.id,
                "status": message.status,
                "media_url": message.media_url,
            }
        )

    except InstagramAPIError as e:
        logger.error(f"Instagram API error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        logger.error(f"Error sending image message: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
@login_required
def get_account_conversations(request: HttpRequest, account_id: int):
    """Get conversations for an Instagram account."""
    try:
        account = get_object_or_404(InstagramAccount, id=account_id)

        # Get recent users with messages
        users = (
            InstagramUser.objects.filter(account=account, messages__isnull=False)
            .distinct()
            .order_by("-last_interaction_at")[:50]
        )

        conversations = []
        for user in users:
            last_message = user.messages.order_by("-timestamp").first()
            conversations.append(
                {
                    "instagram_user_id": user.instagram_user_id,
                    "display_name": user.display_name,
                    "username": user.username,
                    "profile_picture_url": user.profile_picture_url,
                    "customer_id": user.customer.id if user.customer else None,
                    "last_interaction_at": user.last_interaction_at,
                    "total_messages": user.messages.count(),
                    "last_message": (
                        {
                            "text": last_message.text,
                            "message_type": last_message.message_type,
                            "direction": last_message.direction,
                            "timestamp": last_message.timestamp,
                        }
                        if last_message
                        else None
                    ),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "conversations": conversations,
                "account": {
                    "id": account.id,
                    "username": account.username,
                    "name": account.name,
                    "status": account.status,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
@login_required
def get_conversation_messages(
    request: HttpRequest, account_id: int, instagram_user_id: str
):
    """Get messages for a specific conversation."""
    try:
        account = get_object_or_404(InstagramAccount, id=account_id)
        instagram_user = get_object_or_404(
            InstagramUser, instagram_user_id=instagram_user_id, account=account
        )

        # Get messages
        messages = InstagramMessage.objects.filter(
            account=account, instagram_user=instagram_user
        ).order_by("-timestamp")[:100]

        message_list = []
        for message in reversed(messages):  # Show oldest first
            message_list.append(
                {
                    "message_id": message.message_id,
                    "instagram_message_id": message.instagram_message_id,
                    "message_type": message.message_type,
                    "direction": message.direction,
                    "status": message.status,
                    "text": message.text,
                    "media_url": message.media_url,
                    "media_type": message.media_type,
                    "timestamp": message.timestamp,
                    "is_story_reply": message.is_story_reply,
                    "story_id": message.story_id if message.is_story_reply else None,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "messages": message_list,
                "user": {
                    "instagram_user_id": instagram_user.instagram_user_id,
                    "display_name": instagram_user.display_name,
                    "username": instagram_user.username,
                    "profile_picture_url": instagram_user.profile_picture_url,
                    "customer_id": (
                        instagram_user.customer.id if instagram_user.customer else None
                    ),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
@login_required
def get_account_status(request: HttpRequest, account_id: int):
    """Get Instagram account status and health."""
    try:
        account = get_object_or_404(InstagramAccount, id=account_id)

        return JsonResponse(
            {
                "success": True,
                "account": {
                    "id": account.id,
                    "username": account.username,
                    "name": account.name,
                    "instagram_business_account_id": account.instagram_business_account_id,
                    "status": account.status,
                    "is_healthy": account.is_healthy,
                    "health_status": account.health_status,
                    "last_health_check": account.last_health_check,
                    "webhook_subscribed": account.webhook_subscribed,
                    "auto_reply_enabled": account.auto_reply_enabled,
                    "story_replies_enabled": account.story_replies_enabled,
                    "total_messages_sent": account.total_messages_sent,
                    "total_messages_received": account.total_messages_received,
                    "total_story_replies": account.total_story_replies,
                    "followers_count": account.followers_count,
                    "created_at": account.created_at,
                    "updated_at": account.updated_at,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting account status: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def trigger_health_check(request: HttpRequest, account_id: int):
    """Trigger health check for Instagram account."""
    try:
        account = get_object_or_404(InstagramAccount, id=account_id)

        # Perform health check
        message_service = InstagramMessageService(account)
        is_healthy, status_message = message_service.api_client.health_check()

        return JsonResponse(
            {
                "success": True,
                "is_healthy": is_healthy,
                "status_message": status_message,
                "last_health_check": account.last_health_check,
            }
        )

    except Exception as e:
        logger.error(f"Error triggering health check: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@require_http_methods(["GET"])
@login_required
def list_instagram_accounts(request: HttpRequest):
    """List all Instagram accounts."""
    try:
        accounts = InstagramAccount.objects.all().order_by("-created_at")

        account_list = []
        for account in accounts:
            account_list.append(
                {
                    "id": account.id,
                    "username": account.username,
                    "name": account.name,
                    "instagram_business_account_id": account.instagram_business_account_id,
                    "status": account.status,
                    "is_healthy": account.is_healthy,
                    "webhook_subscribed": account.webhook_subscribed,
                    "total_messages_sent": account.total_messages_sent,
                    "total_messages_received": account.total_messages_received,
                    "followers_count": account.followers_count,
                    "created_at": account.created_at,
                }
            )

        return JsonResponse({"success": True, "accounts": account_list})

    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)
