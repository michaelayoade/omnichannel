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

## Performance, Caching & Observability

The backend integrates Redis (DB 2) as a dedicated **cache** instance distinct from the Celery broker (DB 1). Key parts:

1. **Settings** – `CACHES['default']` configured via `REDIS_CACHE_URL` with compression + sensible timeouts.
2. **Utility** – `omnichannel_core.cache.cached_response` decorator caches expensive GET view responses and handles invalidation helpers (`invalidate_model_cache`).
3. **Timeouts** – Controlled by env vars `API_CACHE_SECONDS` (default 60s) and `STATIC_CACHE_SECONDS` (default 1 day).
4. **Docker** – `redis-cache` service added with memory limits (`maxmemory 256mb`, LRU eviction).
5. **Observability** – Sentry SDK, structured logging (`python-json-logger`), Flower dashboard for Celery.

---

## Progressive Web App (PWA)

Front-end now installs as a PWA:
* Offline support via **service-worker.js**
* Static assets: *cache-first*; API calls: *network-first* fallback.
* `UpdateNotification` toast prompts user to refresh when a new version is available.
* `NetworkStatus` toast alerts on offline / online.
* Manifest and meta-tags added in `index.html`.

---

## Role-Based Access Control (RBAC)

Three Django groups are provisioned automatically by migration **0003_create_default_user_groups**:

| Group | Typical User | Permissions |
|-------|--------------|-------------|
| **Agent** | Support agent | Read/modify own conversations & messages, manage quick-reply templates |
| **Supervisor** | Team lead | All agent rights **+** create/delete conversations, view performance snapshots |
| **Admin** | System admin | Full CRUD on all models + system settings |

Custom permission classes in `agent_hub/permissions.py` enforce this in each DRF viewset. Front-end hook `useRoles` exposes groups; `RoleBasedRoute` protects pages.

*Seed users for local testing* (created by `create_test_users.py`):
```
admin / admin123
supervisor / super123
agent / agent123
```

---

## Docker-Compose Quick Start

```bash
# Build & start all services (backend, frontend, redis, redis-cache, db, caddy)
docker-compose up -d --build

# Apply migrations & seed test data
docker-compose exec backend python manage.py migrate
docker-compose exec backend python create_test_users.py
```

Access points:
* Backend API → `http://localhost:8000/api/`
* Swagger → `/api/schema/swagger-ui/`
* Front-end → `http://localhost:3000`
* Flower (task queue monitoring) → `http://localhost:5555`

---

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

---

## Roadmap & Engineering Approach

This section gives the *big-picture* view of where the project is headed and how we intend to get there.  It is a living document – feel free to open a PR if priorities shift.

### Vision
Build a single pane of glass where ISP support agents can handle **all** customer conversations (WhatsApp, Facebook, Instagram, Email, Telegram) and escalate seamlessly into ERPNext tickets – all with real-time updates, smart automation, and robust analytics.

### Phased Roadmap (12-month horizon)
| Phase | Timeline | Theme | High-level Deliverables |
|-------|----------|-------|-------------------------|
| **1. Core Communication Engine** | Months 1-2 | Get WhatsApp live | Conversation schema, WhatsApp API integration, basic agent inbox & assignment |
| **2. Multi-Channel Expansion** | Months 3-4 | 5 channels unified | Facebook Messenger, Instagram DM, Email (IMAP/SMTP), Telegram, unified inbox |
| **3. ERPNext Ticket Integration** | Months 5-6 | Support workflows | Create/update ERPNext tickets from chats, show ticket status & customer data |
| **4. Customer Management & Analytics** | Months 7-8 | Insight | 360° customer profiles, tagging, agent/channel performance dashboards |
| **5. Automation & Workflows** | Months 9-10 | Efficiency | Auto-assignment, SLA alerts, keyword routing, canned templates, follow-ups |
| **6. Advanced Channel Features** | Months 11-12 | Polish & UX | WhatsApp catalog, IG story replies, rich email editor, mobile-optimised UI |

Success metrics for each phase are defined in *docs/roadmap.md* (to be created) and tracked in GitHub Projects.

### Engineering Principles
1. **API-first** – every feature exposed via REST / WebSocket; front-end is a thin client.
2. **Modular services** – separate Django apps per channel, Celery tasks for I/O heavy work.
3. **Security by default** – least-privilege RBAC, secure cookies, rate-limiting, static analysis.
4. **12-factor config** – all secrets and URLs via env vars; Docker Compose for local & VPS.
5. **Quality gates** – lint (ruff, bandit), type-check (mypy), test (pytest) in CI before merge.
6. **Incremental delivery** – vertical slices per phase; always ship something usable.

### How We Work
* GitHub Issues → small, demo-able tasks linked to the roadmap.
* Conventional Commits for clear history (`feat:`, `fix:`, `chore:`).
* PR template requires description, screenshots (if UI), and checklist ticks.
* Weekly demo on Friday; roadmap reviewed monthly.

---
