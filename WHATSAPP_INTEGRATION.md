# WhatsApp Business API Integration

This document provides comprehensive information about the WhatsApp Business API integration for the omnichannel communication platform.

## Overview

The WhatsApp integration provides a complete solution for:

- ✅ **Webhook handlers** for receiving messages (text, media, documents, voice)
- ✅ **Message sending functionality** with proper error handling
- ✅ **Message status tracking** (sent, delivered, read)
- ✅ **Media file processing and storage**
- ✅ **Phone number validation and formatting**
- ✅ **Rate limiting and retry mechanisms**
- ✅ **WhatsApp template message support**
- ✅ **Webhook verification for security**
- ✅ **Django management commands** for testing and monitoring

## Features

### Core Features
- **Multi-message Types**: Text, Image, Audio, Video, Document, Sticker, Location, Contacts
- **Template Messages**: Support for approved WhatsApp message templates
- **Interactive Messages**: Buttons, lists, and other interactive elements
- **Media Processing**: Automatic download and storage of media files
- **Contact Management**: Automatic contact creation and profile updates
- **Conversation Integration**: Seamless integration with the conversations app

### Security Features
- **Webhook Verification**: HMAC-SHA256 signature verification
- **Rate Limiting**: Configurable rate limits per second and per hour
- **Token Management**: Secure storage of access tokens and secrets
- **Error Handling**: Comprehensive error tracking and retry mechanisms

### Monitoring Features
- **Real-time Status Tracking**: Message delivery status updates
- **Health Monitoring**: Built-in monitoring commands
- **Analytics**: Message statistics and performance metrics
- **Logging**: Comprehensive logging for debugging and monitoring

## Installation

### 1. Install Required Packages

```bash
pip install phonenumbers==8.13.0
```

### 2. Update Django Settings

The WhatsApp integration app is already added to `INSTALLED_APPS` in `settings.py`.

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# WhatsApp Settings
WHATSAPP_AUTO_MARK_READ=False
WHATSAPP_DEFAULT_COUNTRY_CODE=1

# Optional: Redis for Celery (recommended for production)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. Run Migrations

```bash
python manage.py migrate whatsapp_integration
```

## Configuration

### 1. Set Up WhatsApp Business Account

Use the management command to set up a new WhatsApp Business Account:

```bash
python manage.py setup_whatsapp_account \
    --name "My Business" \
    --business-account-id "123456789" \
    --phone-number-id "987654321" \
    --access-token "your_access_token" \
    --webhook-verify-token "your_verify_token" \
    --app-id "your_app_id" \
    --app-secret "your_app_secret" \
    --test-connection
```

### 2. Configure Webhook URL

In your Facebook Developer Console, set the webhook URL to:
```
https://your-domain.com/api/whatsapp/webhook/<business_account_id>/
```

### 3. Webhook Verification

The webhook verification token should match the one configured in your WhatsApp Business Account.

## Usage

### Sending Messages

#### Text Message
```python
from whatsapp_integration.services.whatsapp_api import WhatsAppMessageService
from whatsapp_integration.models import WhatsAppBusinessAccount

# Get business account
business_account = WhatsAppBusinessAccount.objects.get(business_account_id="your_id")

# Initialize service
service = WhatsAppMessageService(business_account)

# Send text message
message = service.send_message(
    to="1234567890",
    message_type="text",
    content="Hello from your business!"
)
```

#### Media Message
```python
# Send image with caption
message = service.send_message(
    to="1234567890",
    message_type="image",
    media_url="https://example.com/image.jpg",
    content="Check out this image!"
)
```

#### Template Message
```python
# Send template message
message = service.send_message(
    to="1234567890",
    message_type="template",
    template_name="hello_world",
    template_components=[
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "John"}
            ]
        }
    ]
)
```

### Using Celery Tasks (Recommended for Production)

```python
from whatsapp_integration.tasks import send_whatsapp_message

# Send message asynchronously
send_whatsapp_message.delay(
    business_account_id="your_id",
    to="1234567890",
    message_type="text",
    content="Async message!"
)
```

## Management Commands

### Test Integration
```bash
# Test API connectivity
python manage.py test_whatsapp \
    --business-account-id "your_id" \
    --test-type connectivity

# Send test text message
python manage.py test_whatsapp \
    --business-account-id "your_id" \
    --test-type send-text \
    --to "1234567890" \
    --message "Test message"

# Test template message
python manage.py test_whatsapp \
    --business-account-id "your_id" \
    --test-type send-template \
    --to "1234567890" \
    --template-name "hello_world"

# Get business profile
python manage.py test_whatsapp \
    --business-account-id "your_id" \
    --test-type profile

# List message templates
python manage.py test_whatsapp \
    --business-account-id "your_id" \
    --test-type templates
```

### Monitor Integration
```bash
# Monitor all accounts (last 24 hours)
python manage.py whatsapp_monitor

# Monitor specific account
python manage.py whatsapp_monitor \
    --business-account-id "your_id"

# Monitor with custom time window
python manage.py whatsapp_monitor \
    --business-account-id "your_id" \
    --hours 48

# JSON output for programmatic use
python manage.py whatsapp_monitor \
    --format json
```

## Phone Number Validation

The integration includes comprehensive phone number validation:

```python
from whatsapp_integration.utils.phone_validator import PhoneNumberValidator

# Validate and format phone number
formatted = PhoneNumberValidator.format_for_whatsapp("+1 (555) 123-4567")
print(formatted)  # "15551234567"

# Check if numbers are the same
is_same = PhoneNumberValidator.is_same_number("15551234567", "+1-555-123-4567")
print(is_same)  # True

# Get display format
display = PhoneNumberValidator.get_display_format("15551234567")
print(display)  # "+1 (555) 123-4567"
```

## Rate Limiting

The integration includes automatic rate limiting:

- **Per-second limits**: Configurable (default: 10 requests/second)
- **Per-hour limits**: Configurable (default: 1000 requests/hour)
- **Automatic retry**: Exponential backoff for failed requests
- **Rate limit tracking**: Database tracking of rate limit usage

## Media Handling

### Supported Media Types
- **Images**: JPEG, PNG, GIF
- **Audio**: AAC, MP3, OGG, AMR
- **Video**: MP4, 3GPP
- **Documents**: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX

### Media Processing
- **Automatic download**: Incoming media files are automatically downloaded
- **Storage**: Media files are stored using Django's file storage system
- **Verification**: SHA256 hash verification for file integrity
- **Size limits**: Respects WhatsApp's file size limits

## Webhook Events

The integration handles these webhook events:

### Message Events
- **Incoming messages**: Text, media, location, contacts
- **Message status updates**: Sent, delivered, read, failed

### Account Events
- **Account alerts**: Business account notifications
- **Capability updates**: Feature availability changes

## Error Handling

### API Errors
- **Rate limiting**: Automatic retry with exponential backoff
- **Network errors**: Retry mechanism for transient failures
- **Authentication errors**: Proper error reporting
- **Validation errors**: Input validation before API calls

### Webhook Processing
- **Duplicate prevention**: Webhook event deduplication
- **Retry mechanism**: Failed webhook processing retry
- **Error logging**: Comprehensive error tracking

## Database Models

### WhatsAppBusinessAccount
Stores WhatsApp Business Account configuration and credentials.

### WhatsAppContact
Stores contact information for WhatsApp users.

### WhatsAppMessage
Stores all WhatsApp messages (inbound and outbound) with status tracking.

### WhatsAppTemplate
Stores approved WhatsApp message templates.

### WhatsAppMediaFile
Stores media file information and download status.

### WhatsAppWebhookEvent
Stores webhook events for processing and debugging.

### WhatsAppRateLimit
Tracks rate limiting usage for API calls.

## Security Considerations

### Webhook Security
- **Signature verification**: All webhooks are verified using HMAC-SHA256
- **Token validation**: Webhook verify tokens are validated
- **HTTPS required**: Webhooks should only be received over HTTPS

### Data Protection
- **Token encryption**: Consider encrypting access tokens at rest
- **Log sanitization**: Sensitive data is not logged
- **Access control**: Admin interface requires authentication

## Production Deployment

### Prerequisites
- **Redis**: Required for Celery task queue
- **Celery**: For asynchronous message processing
- **HTTPS**: Required for webhook endpoints
- **File storage**: Configure appropriate file storage for media

### Celery Configuration

Add to your `settings.py`:

```python
# Celery Configuration
CELERY_BEAT_SCHEDULE = {
    'sync-whatsapp-templates': {
        'task': 'whatsapp_integration.tasks.sync_whatsapp_templates',
        'schedule': timedelta(hours=6),
    },
    'cleanup-old-webhook-events': {
        'task': 'whatsapp_integration.tasks.cleanup_old_webhook_events',
        'schedule': timedelta(days=1),
    },
    'retry-failed-messages': {
        'task': 'whatsapp_integration.tasks.retry_failed_messages',
        'schedule': timedelta(minutes=30),
    },
}
```

### Start Celery Workers

```bash
# Start worker
celery -A omnichannel_core worker -l info

# Start beat scheduler
celery -A omnichannel_core beat -l info
```

## Monitoring and Maintenance

### Health Checks
- Monitor webhook processing status
- Track message delivery rates
- Monitor rate limit usage
- Check template approval status

### Maintenance Tasks
- Clean up old webhook events
- Clean up old media files
- Retry failed messages
- Sync message templates

### Logging

The integration logs important events:

```python
import logging

# Configure logging in settings.py
LOGGING = {
    'loggers': {
        'whatsapp_integration': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

## Troubleshooting

### Common Issues

#### Webhook Not Receiving Messages
1. Check webhook URL configuration in Facebook Developer Console
2. Verify webhook verify token matches
3. Check HTTPS certificate validity
4. Review server logs for errors

#### Messages Not Sending
1. Verify access token is valid
2. Check phone number format
3. Review rate limiting status
4. Check template approval status (for template messages)

#### Media Download Failures
1. Check media URL accessibility
2. Verify file size limits
3. Check storage configuration
4. Review download permissions

### Debug Commands

```bash
# Check integration health
python manage.py whatsapp_monitor --business-account-id "your_id"

# Test API connectivity
python manage.py test_whatsapp --business-account-id "your_id" --test-type connectivity

# Review webhook events
python manage.py shell
>>> from whatsapp_integration.models import WhatsAppWebhookEvent
>>> events = WhatsAppWebhookEvent.objects.filter(processing_status='failed')
>>> for event in events:
...     print(f"Event {event.id}: {event.error_message}")
```

## API Reference

### WhatsAppMessageService Methods

- `send_message()`: Send any type of message
- `process_incoming_message()`: Process webhook message events
- `update_message_status()`: Update message delivery status

### WhatsAppBusinessAPI Methods

- `send_text_message()`: Send text message
- `send_media_message()`: Send media message
- `send_template_message()`: Send template message
- `upload_media()`: Upload media file
- `download_media()`: Download media file
- `get_business_profile()`: Get business profile
- `get_templates()`: Get message templates

## Support

For issues and questions:

1. Check the Django admin interface for error details
2. Review application logs
3. Use the monitoring commands to check integration health
4. Refer to WhatsApp Business API documentation for API-specific issues

## License

This WhatsApp integration is part of the omnichannel communication platform.
