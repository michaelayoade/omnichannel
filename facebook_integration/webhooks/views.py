import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import FacebookPage
from .handlers import FacebookWebhookHandler

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class FacebookWebhookView(View):
    """Facebook Messenger webhook endpoint."""

    def get(self, request):
        """Handle webhook verification."""

        # Get verification parameters
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe":
            # Find page with matching verify token
            try:
                page = FacebookPage.objects.get(verify_token=token)
                logger.info(
                    f"Webhook verification successful for page {page.page_name}"
                )
                return HttpResponse(challenge)
            except FacebookPage.DoesNotExist:
                logger.warning(f"Webhook verification failed - invalid token: {token}")
                return HttpResponseForbidden("Invalid verification token")

        return HttpResponseBadRequest("Invalid verification request")

    def post(self, request):
        """Handle incoming webhook events."""

        try:
            # Parse JSON body
            body = json.loads(request.body.decode("utf-8"))

            # Get signature for verification
            signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")

            # Verify object type
            if body.get("object") != "page":
                logger.warning(f"Received non-page webhook: {body.get('object')}")
                return HttpResponseBadRequest("Invalid object type")

            # Process each entry
            entries = body.get("entry", [])

            for entry in entries:
                page_id = entry.get("id")

                try:
                    # Get the Facebook page
                    page = FacebookPage.objects.get(page_id=page_id)

                    # Verify webhook signature
                    if not self._verify_signature(request.body, signature, page):
                        logger.warning(f"Invalid signature for page {page_id}")
                        continue

                    # Process webhook events
                    handler = FacebookWebhookHandler(page)
                    handler.process_webhook_event(body)

                except FacebookPage.DoesNotExist:
                    logger.warning(f"Received webhook for unknown page: {page_id}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing webhook for page {page_id}: {e}")
                    continue

            return HttpResponse("OK")

        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return HttpResponseBadRequest("Processing error")

    def _verify_signature(
        self, body: bytes, signature: str, page: FacebookPage
    ) -> bool:
        """Verify webhook signature."""

        try:
            from ..services.facebook_api import FacebookGraphAPI

            api = FacebookGraphAPI(page)
            return api.verify_webhook_signature(body.decode("utf-8"), signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
def facebook_webhook_endpoint(request):
    """Simple function-based webhook endpoint."""

    if request.method == "GET":
        # Webhook verification
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe":
            try:
                page = FacebookPage.objects.get(verify_token=token)
                logger.info(
                    f"Webhook verification successful for page {page.page_name}"
                )
                return HttpResponse(challenge)
            except FacebookPage.DoesNotExist:
                logger.warning(f"Webhook verification failed - invalid token: {token}")
                return HttpResponseForbidden("Invalid verification token")

        return HttpResponseBadRequest("Invalid verification request")

    elif request.method == "POST":
        # Handle webhook events
        try:
            body = json.loads(request.body.decode("utf-8"))
            signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")

            if body.get("object") != "page":
                return HttpResponseBadRequest("Invalid object type")

            # Process entries
            for entry in body.get("entry", []):
                page_id = entry.get("id")

                try:
                    page = FacebookPage.objects.get(page_id=page_id)

                    # Verify signature
                    from ..services.facebook_api import FacebookGraphAPI

                    api = FacebookGraphAPI(page)
                    if not api.verify_webhook_signature(
                        request.body.decode("utf-8"), signature
                    ):
                        logger.warning(f"Invalid signature for page {page_id}")
                        continue

                    # Process events
                    handler = FacebookWebhookHandler(page)
                    handler.process_webhook_event(body)

                except FacebookPage.DoesNotExist:
                    logger.warning(f"Received webhook for unknown page: {page_id}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing webhook for page {page_id}: {e}")
                    continue

            return HttpResponse("OK")

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return HttpResponseBadRequest("Processing error")


@csrf_exempt
@require_http_methods(["POST"])
def facebook_test_webhook(request):
    """Test webhook endpoint for development."""

    try:
        body = json.loads(request.body.decode("utf-8"))

        logger.info("Test webhook received:")
        logger.info(json.dumps(body, indent=2))

        # Log headers
        logger.info("Headers:")
        for header, value in request.META.items():
            if header.startswith("HTTP_"):
                logger.info(f"  {header}: {value}")

        return HttpResponse("Test webhook received successfully")

    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return HttpResponseBadRequest(f"Error: {e}")
