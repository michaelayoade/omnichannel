# Email Integration Documentation

## Overview

The Email Integration system provides comprehensive email communication capabilities for the omnichannel platform, supporting both SMTP for sending emails and IMAP/POP3 for receiving emails. This integration enables automated email processing, thread detection, customer mapping, and advanced email management features.

## Features

### Core Functionality
- **SMTP Integration**: Send emails via any SMTP provider (Gmail, Outlook, custom servers)
- **IMAP/POP3 Integration**: Receive emails with automatic polling
- **Thread Detection**: Intelligent conversation linking based on subject and message references
- **Attachment Handling**: Support for email attachments with file storage
- **Template Management**: HTML and plain text email templates with variable substitution
- **Bounce Handling**: Automatic detection and processing of bounced emails
- **Customer Mapping**: Automatic linking of emails to existing customers
- **Multi-Account Support**: Support for multiple email accounts (departments, teams)
- **Email Rules**: Automated processing rules for incoming emails
- **Background Processing**: Celery-based asynchronous email processing

### Advanced Features
- **Email Parsing**: Extract customer information from email content
- **Signature Management**: Account-specific signatures and footers
- **Shared Mailbox Support**: Support for both individual and shared email accounts
- **Health Monitoring**: Email account health checks and error tracking
- **Statistics**: Comprehensive email statistics and reporting
- **Rate Limiting**: Built-in rate limiting and retry mechanisms

## Configuration

The Email Integration app can be configured via Django's `settings.py` file. The following settings are available:

- `EMAIL_INTEGRATION_POLL_FREQUENCY`: The default polling frequency in seconds for email accounts. Defaults to `300`.
- `EMAIL_INTEGRATION_MAX_EMAILS_PER_POLL`: The default maximum number of emails to fetch during a single polling cycle. Defaults to `50`.

## Architecture

### Models

#### EmailAccount
Represents an email account configuration:
```python
# Core fields
name = "Support Team"
email_address = "support@company.com"
account_type = "shared"  # individual, shared, department
status = "active"  # active, inactive, error

# SMTP Configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_use_tls = True
smtp_username = "support@company.com"
smtp_password = "app_password"

# IMAP/POP3 Configuration
incoming_protocol = "imap"  # imap, pop3
incoming_server = "imap.gmail.com"
incoming_port = 993
incoming_use_ssl = True
```

#### EmailMessage
Represents individual email messages:
```python
# Message metadata
subject = "Customer inquiry about billing"
from_email = "customer@example.com"
from_name = "John Doe"
direction = "inbound"  # inbound, outbound
status = "received"  # draft, sent, received, failed, bounced

# Content
plain_body = "Plain text content"
html_body = "<html>HTML content</html>"
attachments = [EmailAttachment objects]

# Threading
thread_id = "unique_thread_identifier"
in_reply_to = "parent_message_id"
references = ["list", "of", "message", "ids"]
```

#### EmailThread
Groups related messages into conversations:
```python
thread_id = "unique_identifier"
subject = "Normalized subject"
participants = ["email1@example.com", "email2@example.com"]
message_count = 5
status = "open"  # open, closed, archived
linked_customer = Customer object
```

#### EmailTemplate
Email templates with variable substitution:
```python
name = "Welcome Email"
template_type = "welcome"
subject = "Welcome {{customer_name}}!"
html_content = "<h1>Welcome {{customer_name}}!</h1>"
variables = ["customer_name", "account_name"]
is_global = True  # Available to all accounts
```

### Services

#### SMTPService
Handles outbound email operations:
```python
smtp_service = SMTPService(email_account)

# Send basic email
message = smtp_service.send_email(
    to_emails=["customer@example.com"],
    subject="Response to your inquiry",
    plain_body="Thank you for contacting us...",
    html_body="<p>Thank you for contacting us...</p>"
)

# Send with template
message = smtp_service.send_template_email(
    template_id=1,
    to_emails=["customer@example.com"],
    context={"customer_name": "John Doe"}
)

# Send reply
message = smtp_service.send_reply(
    original_message=original_message,
    reply_body="Thank you for your message..."
)
```

#### IMAPService
Handles inbound email operations:
```python
imap_service = IMAPService(email_account)

# Poll for new emails
poll_log = imap_service.poll_emails(max_emails=50)

# Test connection
success, message = imap_service.test_connection()

# Get folder list
folders = imap_service.get_folder_list()
```

### Background Tasks

#### Email Polling
Automatic polling of email accounts:
```python
# Poll single account
poll_email_account.delay(account_id)

# Poll all accounts (runs every 5 minutes)
poll_all_email_accounts.delay()
```

#### Email Processing
Background processing of emails:
```python
# Send email asynchronously
send_email_task.delay(
    account_id=1,
    to_emails=["customer@example.com"],
    subject="Your inquiry",
    plain_body="Response content..."
)

# Process email rules
process_email_rules.delay(email_message_id)
```

#### Maintenance Tasks
Regular maintenance operations:
```python
# Clean up old emails (daily)
cleanup_old_emails.delay()

# Update statistics (every 6 hours)
update_email_statistics.delay()

# Process bounced emails (hourly)
process_bounced_emails.delay()
```

## Setup and Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Migration

```bash
python manage.py makemigrations email_integration
python manage.py migrate
```

### 3. Environment Configuration

Add to your `.env` file:
```bash
# Email Integration Settings
EMAIL_RETENTION_DAYS=365
EMAIL_MAX_ATTACHMENT_SIZE=26214400  # 25MB
EMAIL_DEFAULT_POLL_FREQUENCY=300    # 5 minutes
EMAIL_MAX_RETRY_ATTEMPTS=3

# Celery Configuration (if not already set)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. Create Email Account

Using Django admin or programmatically:
```python
from email_integration.models import EmailAccount

account = EmailAccount.objects.create(
    name="Customer Support",
    email_address="support@yourcompany.com",
    account_type="shared",
    department="Customer Service",

    # SMTP Configuration
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    smtp_use_tls=True,
    smtp_username="support@yourcompany.com",
    smtp_password="your_app_password",

    # IMAP Configuration
    incoming_protocol="imap",
    incoming_server="imap.gmail.com",
    incoming_port=993,
    incoming_use_ssl=True,
    incoming_username="support@yourcompany.com",
    incoming_password="your_app_password",

    # Settings
    auto_polling_enabled=True,
    poll_frequency=300,  # 5 minutes
    max_emails_per_poll=50
)
```

### 5. Start Celery Workers

```bash
# Start Celery worker
celery -A omnichannel_core worker -l info

# Start Celery beat scheduler (in separate terminal)
celery -A omnichannel_core beat -l info
```

## Usage Examples

### Sending Emails

#### Basic Email
```python
from email_integration.services.smtp_service import SMTPService
from email_integration.models import EmailAccount

account = EmailAccount.objects.get(email_address="support@company.com")
smtp_service = SMTPService(account)

message = smtp_service.send_email(
    to_emails=["customer@example.com"],
    subject="Thank you for your inquiry",
    plain_body="We have received your message and will respond soon.",
    html_body="<p>We have received your message and will respond soon.</p>"
)
```

#### Email with Attachments
```python
from django.core.files.base import ContentFile

attachment_content = ContentFile(b"File content", name="document.pdf")

message = smtp_service.send_email(
    to_emails=["customer@example.com"],
    subject="Your requested document",
    plain_body="Please find the attached document.",
    attachments=[attachment_content]
)
```

#### Template Email
```python
from email_integration.models import EmailTemplate

template = EmailTemplate.objects.create(
    name="Welcome Email",
    subject="Welcome {{customer_name}}!",
    html_content="<h1>Welcome {{customer_name}}!</h1><p>Thank you for joining us.</p>",
    variables=["customer_name"]
)

message = smtp_service.send_template_email(
    template=template,
    to_emails=["customer@example.com"],
    context={"customer_name": "John Doe"}
)
```

### Receiving Emails

#### Manual Polling
```python
from email_integration.services.imap_service import IMAPService

imap_service = IMAPService(account)
poll_log = imap_service.poll_emails(max_emails=10)

print(f"Found {poll_log.messages_found} messages")
print(f"Processed {poll_log.messages_processed} messages")
```

#### Processing New Messages
```python
from email_integration.models import EmailMessage

# Get recent unprocessed messages
new_messages = EmailMessage.objects.filter(
    account=account,
    direction="inbound",
    status="received"
).order_by("-received_at")[:10]

for message in new_messages:
    print(f"From: {message.from_email}")
    print(f"Subject: {message.subject}")
    print(f"Thread: {message.thread_id}")
```

### Email Rules

#### Auto-Reply Rule
```python
from email_integration.models import EmailRule

rule = EmailRule.objects.create(
    account=account,
    name="Auto-reply for new customers",
    rule_type="auto_reply",
    condition_type="from_contains",
    condition_value="@newcustomer.com",
    action_data={
        "template_id": template.id
    },
    priority=1,
    is_active=True
)
```

#### Forward Rule
```python
rule = EmailRule.objects.create(
    account=account,
    name="Forward urgent emails",
    rule_type="forward",
    condition_type="subject_contains",
    condition_value="urgent",
    action_data={
        "forward_to": ["manager@company.com"],
        "include_attachments": True
    },
    priority=2,
    is_active=True
)
```

## Management Commands

### Test Email Connectivity
```bash
# Test all connections for an account
python manage.py test_email_connectivity --email-address support@company.com

# Test only SMTP
python manage.py test_email_connectivity --account-id 1 --test-type smtp

# Send test email
python manage.py test_email_connectivity \
    --account-id 1 \
    --send-test-email \
    --to-email test@example.com
```

### Manual Email Polling
```bash
# Poll specific account
python manage.py poll_emails --email-address support@company.com

# Poll all accounts
python manage.py poll_emails --all-accounts

# Force poll (ignore disabled polling)
python manage.py poll_emails --all-accounts --force
```

### Monitor Email Integration
```bash
# Show monitoring dashboard
python manage.py email_monitor

# Monitor specific account
python manage.py email_monitor --email-address support@company.com

# Show detailed errors
python manage.py email_monitor --show-errors

# JSON output for automation
python manage.py email_monitor --format json
```

## Email Provider Configuration

### Gmail Setup
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use these settings:
   - SMTP: smtp.gmail.com:587 (TLS)
   - IMAP: imap.gmail.com:993 (SSL)

### Outlook/Office 365
1. Enable IMAP in account settings
2. Use app password or OAuth2
3. Settings:
   - SMTP: smtp-mail.outlook.com:587 (TLS)
   - IMAP: outlook.office365.com:993 (SSL)

### Custom SMTP Server
Configure based on your provider's documentation.

## Security Considerations

### Password Security
- Use app-specific passwords when available
- Store passwords securely using environment variables
- Rotate passwords regularly

### SSL/TLS Configuration
- Always use SSL/TLS for email connections
- Verify certificate validity
- Use appropriate ports (587 for SMTP with TLS, 993 for IMAP with SSL)

### Data Protection
- Encrypt sensitive email content
- Implement proper access controls
- Regular security audits

## Troubleshooting

### Common Issues

#### Connection Errors
```python
# Test connectivity
python manage.py test_email_connectivity --email-address your@email.com

# Check account health
account = EmailAccount.objects.get(email_address="your@email.com")
print(f"Healthy: {account.is_healthy}")
print(f"Last error: {account.last_error_message}")
```

#### Authentication Failures
- Verify username/password combinations
- Check if 2FA is enabled (use app passwords)
- Ensure IMAP is enabled for the account

#### Polling Issues
```python
# Check recent poll logs
from email_integration.models import EmailPollLog

recent_polls = EmailPollLog.objects.filter(
    account=account
).order_by("-started_at")[:5]

for poll in recent_polls:
    print(f"Status: {poll.status}")
    print(f"Error: {poll.error_message}")
```

### Debug Mode
Enable detailed logging in settings:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'email_integration': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Performance Optimization

### Polling Optimization
- Adjust poll frequency based on email volume
- Use incremental polling for large mailboxes
- Monitor poll performance with EmailPollLog

### Database Optimization
- Regular cleanup of old messages
- Index optimization for frequently queried fields
- Archive old threads to separate storage

### Celery Optimization
- Scale worker processes based on load
- Use separate queues for different priority emails
- Monitor task execution times

## API Integration

### REST API Endpoints
The email integration provides REST API endpoints for external access:

```python
# Send email via API
POST /api/email/send/
{
    "account_id": 1,
    "to_emails": ["customer@example.com"],
    "subject": "API Test",
    "plain_body": "Test message"
}

# Get account messages
GET /api/email/accounts/1/messages/

# Get thread messages
GET /api/email/threads/{thread_id}/messages/
```

## Monitoring and Analytics

### Health Monitoring
- Account connection status
- Email processing rates
- Error tracking and alerting
- Performance metrics

### Analytics
- Email volume trends
- Response time analysis
- Customer engagement metrics
- Thread resolution rates

## Future Enhancements

### Planned Features
- OAuth2 authentication support
- Advanced spam filtering
- Email encryption (PGP/S-MIME)
- Calendar integration
- Mobile push notifications
- AI-powered email categorization

### Integration Possibilities
- CRM system integration
- Helpdesk ticket creation
- Knowledge base suggestions
- Sentiment analysis
- Language translation

## Support

For technical support or feature requests:
1. Check the troubleshooting section
2. Review the Django admin interface for configuration
3. Use management commands for diagnostics
4. Monitor Celery task logs for background processing issues

The email integration system is designed to be robust, scalable, and maintainable, providing a solid foundation for email communication in your omnichannel platform.
