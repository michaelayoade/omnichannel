# Omnichannel Communication MVP

A Django-based omnichannel communication platform that integrates with Splynx ISP management system.

## Features

- **Multi-channel Communication**: Support for Email, SMS, WhatsApp, Facebook Messenger, Telegram, Web Chat, and more
- **Splynx Integration**: Seamless synchronization with Splynx customer data, services, tickets, and invoices
- **Agent Management**: Complete agent workflow with availability, skills, and workload management
- **Real-time Messaging**: WebSocket support for real-time communication
- **Customer Management**: Unified customer profiles across all channels
- **Conversation Tracking**: Complete conversation history and analytics
- **Security-First Design**: Secure cryptographic practices, proper rate limiting, and input validation

## Project Structure

```
omnichannel-mvp/
├── omnichannel_core/          # Django project settings
├── customers/                 # Customer management app
├── agents/                    # Agent management app
├── communication_channels/    # Channel configuration app
├── conversations/             # Conversation and message handling
├── splynx_sync/              # Splynx integration app
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
└── manage.py               # Django management script
```

## Installation

1. **Clone and setup the project:**
   ```bash
   cd omnichannel-mvp
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

## Apps Overview

### Customers App
- Customer model with Splynx integration
- Customer services tracking
- Customer profile management

### Agents App
- Agent profiles and authentication
- Skill-based routing
- Availability management
- Workload tracking

### Communication Channels App
- Multi-platform channel configuration
- Channel integrations (API keys, webhooks)
- Contact management across channels

### Conversations App
- Unified conversation interface
- Message handling across all channels
- Conversation participants and notes
- Real-time message delivery

### Splynx Sync App
- Bi-directional data synchronization
- Webhook event processing
- Customer, service, ticket, and invoice mapping
- Sync logging and error handling

## API Documentation

Once the server is running, visit:
- API Documentation: http://localhost:8000/api/schema/swagger-ui/
- Admin Interface: http://localhost:8000/admin/

## Configuration

### Database
The project uses SQLite by default. For production, configure PostgreSQL in your `.env` file.

### Redis
Required for Celery and Channels. Install Redis and configure the `REDIS_URL` in your `.env` file.

### Splynx Integration
Configure your Splynx API credentials in the `.env` file to enable synchronization.

## Development

### Adding New Channels
1. Extend the `CommunicationChannel` model choices
2. Create channel-specific integration handlers
3. Implement webhook processors for incoming messages

### Extending Splynx Integration
1. Add new sync types to `SplynxSyncLog`
2. Create corresponding mapping models
3. Implement sync tasks in Celery

### Security & Code Quality
See [Security Improvements Documentation](docs/security-improvements.md) for details on:
- Security audits and fixes
- Magic number elimination 
- Type hints and modern Python syntax
- Control flow improvements
- Development best practices

## Running Tests & Checks

```bash
# Run the full test suite
python manage.py test

# Run security checks
bandit -r . --exclude .venv,migrations,tests

# Run code quality checks
ruff .

# Run type checking
mypy .
```

## Next Steps

1. Set up webhook endpoints for channel integrations
2. Implement real-time WebSocket consumers
3. Add API serializers and viewsets
4. Create Celery tasks for background processing
5. Add comprehensive testing suite
6. Implement frontend interface
