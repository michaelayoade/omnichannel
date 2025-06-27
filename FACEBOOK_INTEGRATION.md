# Facebook Messenger Integration Documentation

## Overview

The Facebook Messenger Integration system provides comprehensive communication capabilities for the omnichannel platform, enabling seamless interaction with customers through Facebook Messenger. This integration supports rich messaging features, automated conversation flows, customer profile management, and advanced webhook handling.

## Features

### Core Functionality
- **Facebook Graph API Integration**: Send and receive messages via Facebook Messenger
- **Rich Media Support**: Images, videos, audio files, and document attachments
- **Template Messages**: Button templates, generic templates (carousels), and list templates
- **Quick Replies**: Interactive quick reply buttons for streamlined conversations
- **User Profile Management**: Automatic profile retrieval and customer matching
- **Webhook Security**: Comprehensive webhook verification and signature validation
- **Message Delivery Tracking**: Real-time delivery and read receipt processing

### Advanced Features
- **Conversation Flows**: Automated conversation flows with conditional logic
- **Lead Generation**: Built-in lead capture and qualification workflows
- **Customer Service Flows**: Intelligent routing and escalation systems
- **Persistent Menu**: Customizable persistent menu for consistent navigation
- **Get Started Button**: Welcome flow triggers for new conversations
- **Handover Protocol**: Seamless transitions between automated and live chat
- **Multi-Page Support**: Manage multiple Facebook pages from one platform
- **Rate Limiting**: Built-in rate limiting and retry mechanisms
- **Error Handling**: Comprehensive error tracking and recovery

## Architecture

### Models

#### FacebookPage
Represents a Facebook Page configuration:
```python
# Core fields
page_name = "Customer Support"
page_id = "1234567890123456"
page_access_token = "long_lived_page_access_token"
app_id = "your_facebook_app_id"
app_secret = "your_facebook_app_secret"

# Webhook Configuration
webhook_url = "https://yoursite.com/api/facebook/webhook/"
verify_token = "your_webhook_verify_token"
webhook_subscribed = True

# Status and Health
status = "active"  # active, inactive, error, pending
is_healthy = True
```

#### FacebookUser
Represents a Facebook Messenger user:
```python
# Facebook Information
psid = "user_page_scoped_id"
page = FacebookPage object

# Profile Information
first_name = "John"
last_name = "Doe"
profile_pic = "https://facebook.com/profile.jpg"
locale = "en_US"
timezone = -5
gender = "male"

# Customer Linking
customer = Customer object  # Linked to existing customer
```

#### FacebookMessage
Represents individual messages:
```python
# Message metadata
message_id = "unique_message_id"
facebook_message_id = "facebook_mid"
direction = "inbound"  # inbound, outbound
message_type = "text"  # text, image, video, audio, file, template, etc.
status = "sent"  # pending, sent, delivered, read, failed

# Content
text = "Hello! How can I help you?"
attachment_url = "https://example.com/image.jpg"
quick_reply_payload = "PAYLOAD_DATA"

# Delivery Tracking
sent_at = datetime
delivered_at = datetime
read_at = datetime
```

#### FacebookTemplate
Reusable message templates:
```python
name = "Welcome Message"
template_type = "button"  # button, generic, list
template_data = {
    "template_type": "button",
    "text": "Welcome! How can we help?",
    "buttons": [
        {"type": "postback", "title": "Get Started", "payload": "GET_STARTED"}
    ]
}
variables = ["user_name", "page_name"]
```

#### FacebookConversationFlow
Automated conversation flows:
```python
name = "Welcome Flow"
flow_type = "welcome"  # welcome, lead_generation, customer_service, etc.
trigger_type = "get_started"  # get_started, keyword, postback, referral
trigger_value = "GET_STARTED"
flow_steps = {
    "start": {
        "actions": [
            {"type": "send_text", "text": "Hello {{first_name}}!"}
        ],
        "next": "ask_help"
    }
}
```

### Services

#### FacebookGraphAPI
Low-level API client for Facebook Graph API:
```python
api = FacebookGraphAPI(facebook_page)

# Send text message
success, response = api.send_text_message(
    recipient_id="user_psid",
    text="Hello! How can I help you?"
)

# Send template message
success, response = api.send_template_message(
    recipient_id="user_psid",
    template_data={
        "template_type": "button",
        "text": "Choose an option:",
        "buttons": [
            {"type": "postback", "title": "Support", "payload": "SUPPORT"}
        ]
    }
)

# Get user profile
success, profile = api.get_user_profile(user_id="user_psid")
```

#### FacebookMessengerService
High-level messaging service:
```python
messenger = FacebookMessengerService(facebook_page)

# Send text message
message = messenger.send_text(
    recipient_psid="user_psid",
    text="Thank you for your message!"
)

# Send image
message = messenger.send_image(
    recipient_psid="user_psid",
    image_url="https://example.com/image.jpg"
)

# Send button template
message = messenger.send_button_template(
    recipient_psid="user_psid",
    text="What would you like to do?",
    buttons=[
        {"type": "postback", "title": "Get Help", "payload": "HELP"},
        {"type": "web_url", "title": "Visit Website", "url": "https://example.com"}
    ]
)

# Send quick replies
message = messenger.send_quick_reply(
    recipient_psid="user_psid",
    text="How can we help you today?",
    quick_replies=[
        {"content_type": "text", "title": "Support", "payload": "SUPPORT"},
        {"content_type": "text", "title": "Sales", "payload": "SALES"}
    ]
)
```

### Webhook Handling

#### FacebookWebhookHandler
Processes incoming webhook events:
```python
handler = FacebookWebhookHandler(facebook_page)

# Process webhook event
success = handler.process_webhook_event(webhook_data)

# Automatic handling of:
# - Incoming messages
# - Postback events (button clicks)
# - Delivery confirmations
# - Read receipts
# - Opt-in events
# - Referral events
# - Handover protocol events
```

## Setup and Configuration

### 1. Facebook App Setup

1. **Create Facebook App**:
   - Go to [Facebook Developers](https://developers.facebook.com/)
   - Create a new app with "Business" type
   - Add "Messenger" product to your app

2. **Configure Messenger Product**:
   - Add your Facebook Page
   - Generate Page Access Token
   - Set up webhook URL: `https://yoursite.com/api/facebook/webhook/`

3. **Webhook Configuration**:
   - Subscribe to webhook events: messages, messaging_postbacks, messaging_optins, etc.
   - Set verify token in your app settings

### 2. Django Configuration

Add to your `.env` file:
```bash
# Facebook Integration Settings
FACEBOOK_WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_MAX_MESSAGE_RETRY=3
FACEBOOK_RATE_LIMIT_PER_HOUR=1000
```

### 3. Database Migration

```bash
python manage.py makemigrations facebook_integration
python manage.py migrate
```

### 4. Setup Facebook Page

```bash
python manage.py setup_facebook_page \
    --page-id YOUR_PAGE_ID \
    --page-access-token YOUR_PAGE_ACCESS_TOKEN \
    --app-id YOUR_APP_ID \
    --app-secret YOUR_APP_SECRET \
    --verify-token YOUR_VERIFY_TOKEN \
    --configure-profile
```

### 5. Test Webhook

```bash
python manage.py test_facebook_webhook \
    --page-id YOUR_PAGE_ID \
    --verify-webhook \
    --subscribe-webhook
```

## Usage Examples

### Sending Messages

#### Basic Text Message
```python
from facebook_integration.services.facebook_api import FacebookMessengerService
from facebook_integration.models import FacebookPage

page = FacebookPage.objects.get(page_id="YOUR_PAGE_ID")
messenger = FacebookMessengerService(page)

message = messenger.send_text(
    recipient_psid="user_psid",
    text="Hello! Thank you for contacting us."
)
```

#### Rich Media Messages
```python
# Send image
message = messenger.send_image(
    recipient_psid="user_psid",
    image_url="https://example.com/product-image.jpg"
)

# Send video
message = messenger.send_video(
    recipient_psid="user_psid",
    video_url="https://example.com/demo-video.mp4"
)

# Send file
message = messenger.send_file(
    recipient_psid="user_psid",
    file_url="https://example.com/brochure.pdf"
)
```

#### Template Messages
```python
# Button template
message = messenger.send_button_template(
    recipient_psid="user_psid",
    text="What would you like to do?",
    buttons=[
        {
            "type": "postback",
            "title": "Get Support",
            "payload": "SUPPORT"
        },
        {
            "type": "web_url",
            "title": "Visit Website",
            "url": "https://example.com",
            "webview_height_ratio": "tall"
        },
        {
            "type": "phone_number",
            "title": "Call Us",
            "payload": "+1-555-123-4567"
        }
    ]
)

# Generic template (carousel)
message = messenger.send_generic_template(
    recipient_psid="user_psid",
    elements=[
        {
            "title": "Product 1",
            "subtitle": "Amazing product description",
            "image_url": "https://example.com/product1.jpg",
            "default_action": {
                "type": "web_url",
                "url": "https://example.com/product1"
            },
            "buttons": [
                {
                    "type": "postback",
                    "title": "Buy Now",
                    "payload": "BUY_PRODUCT_1"
                }
            ]
        },
        {
            "title": "Product 2",
            "subtitle": "Another great product",
            "image_url": "https://example.com/product2.jpg",
            "buttons": [
                {
                    "type": "postback",
                    "title": "Learn More",
                    "payload": "INFO_PRODUCT_2"
                }
            ]
        }
    ]
)
```

#### Quick Replies
```python
message = messenger.send_quick_reply(
    recipient_psid="user_psid",
    text="How can we help you today?",
    quick_replies=[
        {
            "content_type": "text",
            "title": "Technical Support",
            "payload": "TECH_SUPPORT",
            "image_url": "https://example.com/tech-icon.png"
        },
        {
            "content_type": "text",
            "title": "Billing Question",
            "payload": "BILLING",
            "image_url": "https://example.com/billing-icon.png"
        },
        {
            "content_type": "text",
            "title": "General Inquiry",
            "payload": "GENERAL"
        }
    ]
)
```

### Using Templates

#### Create Template
```python
from facebook_integration.models import FacebookTemplate

template = FacebookTemplate.objects.create(
    name="Welcome Template",
    template_type="button",
    page=page,
    template_data={
        "template_type": "button",
        "text": "Welcome {{user_name}}! How can we help you?",
        "buttons": [
            {
                "type": "postback",
                "title": "Get Started",
                "payload": "GET_STARTED"
            },
            {
                "type": "postback",
                "title": "Browse Products",
                "payload": "BROWSE_PRODUCTS"
            }
        ]
    },
    variables=["user_name"]
)

# Send template message
message = messenger.send_template_message(
    recipient_psid="user_psid",
    template=template,
    variables={"user_name": "John"}
)
```

### Conversation Flows

#### Create Welcome Flow
```python
python manage.py create_facebook_flow \
    --page-id YOUR_PAGE_ID \
    --flow-type welcome
```

#### Custom Flow Example
```python
from facebook_integration.models import FacebookConversationFlow

flow = FacebookConversationFlow.objects.create(
    name="Lead Generation Flow",
    flow_type="lead_generation",
    page=page,
    trigger_type="keyword",
    trigger_value="interested,demo,pricing",
    flow_steps={
        "start": {
            "actions": [
                {
                    "type": "send_text",
                    "text": "Great! I'd love to learn more about your needs."
                },
                {
                    "type": "send_text",
                    "text": "What's your name?"
                }
            ],
            "next": "collect_name"
        },
        "collect_name": {
            "actions": [
                {
                    "type": "set_variable",
                    "name": "lead_name",
                    "value": "{{message_text}}"
                },
                {
                    "type": "send_text",
                    "text": "Nice to meet you, {{lead_name}}!"
                },
                {
                    "type": "send_text",
                    "text": "What's your email address?"
                }
            ],
            "next": "collect_email"
        },
        "collect_email": {
            "actions": [
                {
                    "type": "set_variable",
                    "name": "lead_email",
                    "value": "{{message_text}}"
                },
                {
                    "type": "send_text",
                    "text": "Perfect! Our sales team will contact you at {{lead_email}} within 24 hours."
                }
            ],
            "next": "end"
        },
        "end": {
            "actions": [
                {
                    "type": "send_text",
                    "text": "Thank you for your interest! 🚀"
                }
            ]
        }
    },
    is_active=True,
    priority=8
)
```

### Page Configuration

#### Set Up Persistent Menu
```python
messenger.configure_page_settings({
    'persistent_menu': [
        {
            "type": "postback",
            "title": "Get Started",
            "payload": "GET_STARTED"
        },
        {
            "type": "nested",
            "title": "Help",
            "call_to_actions": [
                {
                    "type": "postback",
                    "title": "Contact Support",
                    "payload": "CONTACT_SUPPORT"
                },
                {
                    "type": "postback",
                    "title": "FAQ",
                    "payload": "FAQ"
                },
                {
                    "type": "web_url",
                    "title": "Help Center",
                    "url": "https://example.com/help"
                }
            ]
        },
        {
            "type": "web_url",
            "title": "Visit Website",
            "url": "https://example.com"
        }
    ],
    'greeting_text': "Hi! Welcome to our page. How can we help you today?",
    'get_started_payload': "GET_STARTED",
    'ice_breakers': [
        {
            "question": "What services do you offer?",
            "payload": "SERVICES"
        },
        {
            "question": "How can I contact support?",
            "payload": "SUPPORT"
        }
    ]
})
```

### Handover Protocol

#### Pass Control to Live Agent
```python
# In your conversation flow or message handler
if user_needs_human_agent:
    api = FacebookGraphAPI(page)
    success, response = api.pass_thread_control(
        recipient_id="user_psid",
        target_app_id="page_inbox_app_id",  # Facebook Page Inbox
        metadata="Customer requested human agent"
    )
```

#### Take Control Back
```python
# When agent is done
success, response = api.take_thread_control(
    recipient_id="user_psid",
    metadata="Automated system resuming"
)
```

## Management Commands

### Setup Facebook Page
```bash
# Complete page setup
python manage.py setup_facebook_page \
    --page-id 1234567890123456 \
    --page-access-token "your_page_access_token" \
    --app-id "your_app_id" \
    --app-secret "your_app_secret" \
    --verify-token "your_verify_token" \
    --webhook-url "https://yoursite.com/api/facebook/webhook/" \
    --configure-profile \
    --test-connection
```

### Test Webhook
```bash
# Test webhook verification
python manage.py test_facebook_webhook \
    --page-id 1234567890123456 \
    --verify-webhook

# Subscribe to webhook
python manage.py test_facebook_webhook \
    --page-id 1234567890123456 \
    --subscribe-webhook

# Send test message
python manage.py test_facebook_webhook \
    --page-id 1234567890123456 \
    --test-message "Hello from Django!" \
    --recipient-psid "user_psid"

# List webhook subscriptions
python manage.py test_facebook_webhook \
    --page-id 1234567890123456 \
    --list-subscriptions
```

### Monitor Integration
```bash
# Show monitoring dashboard
python manage.py facebook_monitor

# Monitor specific page
python manage.py facebook_monitor --page-id 1234567890123456

# Show detailed errors and flows
python manage.py facebook_monitor \
    --page-id 1234567890123456 \
    --show-errors \
    --show-flows \
    --show-users

# JSON output for automation
python manage.py facebook_monitor --format json
```

### Create Conversation Flows
```bash
# Create welcome flow
python manage.py create_facebook_flow \
    --page-id 1234567890123456 \
    --flow-type welcome

# Create lead generation flow
python manage.py create_facebook_flow \
    --page-id 1234567890123456 \
    --flow-type lead_generation

# Create all predefined flows
python manage.py create_facebook_flow \
    --page-id 1234567890123456 \
    --flow-type all \
    --force  # Overwrite existing
```

## Webhook Events

### Supported Events

The integration handles the following webhook events:

#### Messages
- Text messages
- Image/video/audio attachments
- Files and documents
- Stickers
- Location sharing
- Quick reply responses

#### Messaging Events
- **messaging_postbacks**: Button clicks and menu selections
- **messaging_optins**: User opt-ins and confirmations
- **messaging_referrals**: Referral parameter tracking
- **messaging_handovers**: Handover protocol events
- **message_deliveries**: Delivery confirmations
- **message_reads**: Read receipts

#### Event Processing
All events are:
1. Verified for authenticity using webhook signatures
2. Logged in `FacebookWebhookEvent` model
3. Processed asynchronously for reliability
4. Linked to appropriate users and conversations
5. Routed through conversation flows when applicable

### Webhook Security

The integration implements comprehensive security measures:

```python
# Signature verification
def verify_webhook_signature(payload: str, signature: str) -> bool:
    expected_signature = hmac.new(
        app_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(signature[5:], expected_signature)

# Request validation
def validate_webhook_request(request):
    # Verify signature
    # Check content type
    # Validate JSON structure
    # Verify page ownership
```

## API Reference

### Helper Functions

#### Message Components
```python
from facebook_integration.services.facebook_api import (
    create_quick_reply, create_postback_button, create_url_button,
    create_call_button, create_generic_element, create_list_element
)

# Create quick reply
quick_reply = create_quick_reply(
    title="Support",
    payload="SUPPORT",
    image_url="https://example.com/icon.png"
)

# Create postback button
button = create_postback_button(
    title="Get Started",
    payload="GET_STARTED"
)

# Create URL button
url_button = create_url_button(
    title="Visit Website",
    url="https://example.com",
    webview_height_ratio="tall"
)

# Create call button
call_button = create_call_button(
    title="Call Us",
    phone_number="+1-555-123-4567"
)

# Create carousel element
element = create_generic_element(
    title="Product Name",
    subtitle="Product description",
    image_url="https://example.com/product.jpg",
    default_action=create_url_button("View", "https://example.com/product"),
    buttons=[create_postback_button("Buy", "BUY_PRODUCT")]
)
```

### Rate Limiting

```python
from facebook_integration.services.facebook_api import FacebookRateLimiter

rate_limiter = FacebookRateLimiter(page, max_calls_per_hour=1000)

if rate_limiter.can_make_call():
    # Make API call
    rate_limiter.record_call()
else:
    wait_time = rate_limiter.get_wait_time()
    # Wait or queue for later
```

## Troubleshooting

### Common Issues

#### Webhook Verification Fails
```bash
# Check webhook configuration
python manage.py test_facebook_webhook \
    --page-id YOUR_PAGE_ID \
    --verify-webhook

# Common causes:
# - Incorrect verify token
# - HTTPS not properly configured
# - Firewall blocking Facebook IPs
```

#### Messages Not Sending
```python
# Check page health
page = FacebookPage.objects.get(page_id="YOUR_PAGE_ID")
print(f"Healthy: {page.is_healthy}")
print(f"Last error: {page.last_error_message}")

# Test connection
messenger = FacebookMessengerService(page)
success, message = messenger.test_connection()
print(f"Connection: {success}, {message}")
```

#### User Profile Not Loading
```python
# Check user profile data
user = FacebookUser.objects.get(psid="USER_PSID")
if not user.first_name:
    # Manually fetch profile
    api = FacebookGraphAPI(page)
    success, profile = api.get_user_profile(user.psid)
    if success:
        user.first_name = profile.get('first_name', '')
        user.last_name = profile.get('last_name', '')
        user.save()
```

### Debug Mode

Enable detailed logging:
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'facebook_integration': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Performance Optimization

#### Database Optimization
- Regular cleanup of old webhook events
- Index optimization for frequently queried fields
- Archive old conversations to separate storage

#### API Optimization
- Use reusable attachment IDs for media
- Batch API calls when possible
- Implement proper caching for user profiles

#### Flow Optimization
- Monitor flow completion rates
- A/B test different flow variations
- Optimize based on user engagement metrics

## Security Considerations

### Data Protection
- Store access tokens securely using environment variables
- Encrypt sensitive user data
- Implement proper access controls
- Regular security audits

### Rate Limiting
- Respect Facebook's rate limits
- Implement exponential backoff
- Queue messages during high traffic
- Monitor API usage

### Webhook Security
- Always verify webhook signatures
- Use HTTPS for all webhook endpoints
- Validate all incoming data
- Log security events

## Monitoring and Analytics

### Health Monitoring
- Page connection status
- Message delivery rates
- Webhook processing success
- API error tracking

### Analytics
- Message volume trends
- User engagement metrics
- Conversation flow performance
- Customer satisfaction scores

### Alerts
Set up monitoring for:
- Failed webhook deliveries
- High error rates
- API quota approaching limits
- Unusual traffic patterns

## Integration with Other Systems

### CRM Integration
- Automatic customer profile creation
- Lead scoring and qualification
- Activity logging and tracking
- Follow-up automation

### Support Ticket Integration
- Automatic ticket creation for complex issues
- Agent assignment based on skills
- Conversation history transfer
- SLA tracking

### Analytics Integration
- Google Analytics event tracking
- Custom metrics and KPIs
- A/B testing frameworks
- Performance monitoring

## Best Practices

### Message Design
- Keep messages concise and clear
- Use rich media to enhance engagement
- Provide clear call-to-action buttons
- Test messages across different devices

### Conversation Flows
- Design intuitive user journeys
- Provide escape hatches and help options
- Use progressive disclosure for complex flows
- Regular testing and optimization

### Customer Experience
- Respond quickly to user messages
- Personalize interactions when possible
- Provide seamless handoff to human agents
- Maintain conversation context

### Development
- Use version control for flow configurations
- Implement proper error handling
- Write comprehensive tests
- Document custom flows and integrations

## Future Enhancements

### Planned Features
- AI-powered message understanding
- Advanced customer segmentation
- Multi-language support
- Voice message support
- Integration with Instagram Direct
- Enhanced analytics dashboard

### API Improvements
- GraphQL API support
- Real-time subscription updates
- Bulk operations API
- Advanced webhook filtering

The Facebook Messenger integration provides a robust foundation for customer communication, with enterprise-grade features for scalability, security, and user experience. The comprehensive flow system and webhook handling ensure reliable message delivery and processing, while the management commands and monitoring tools provide operational excellence.
