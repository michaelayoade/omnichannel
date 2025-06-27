# Deployment Guide

## Required GitHub Secrets

To deploy this application via GitHub Actions, you need to configure the following secrets in your repository settings:

### Required Secrets:
1. `DEPLOY_SSH_KEY` - Private SSH key for server access
2. `DEPLOY_USER` - Username for deployment server
3. `DEPLOY_HOST` - Hostname/IP of deployment server
4. `DEPLOY_PATH` - Path on server where app will be deployed
5. `DJANGO_SECRET_KEY` - Django secret key for production
6. `ENCRYPTION_KEY` - Application encryption key
7. `REDIS_PASSWORD` - Redis password for production
8. `POSTGRES_PASSWORD` - PostgreSQL password for production
9. `SENTRY_DSN` - Sentry DSN for error tracking
10. `SLACK_WEBHOOK` - Slack webhook URL for notifications

### Local Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

3. Run with Daphne (for WebSocket support):
   ```bash
   daphne -p 8000 omnichannel_core.asgi:application
   ```

4. Access the application:
   - Admin: http://localhost:8000/admin/
   - Login: http://localhost:8000/accounts/login/
   - Dashboard: http://localhost:8000/api/agent_hub/dashboard/

### WebSocket Testing

WebSocket endpoints are available at:
- Agent Status: `ws://localhost:8000/ws/agent/status/`
- Notifications: `ws://localhost:8000/ws/agent/notifications/`

### Security Checklist

- [ ] All secrets are stored in GitHub Secrets (not committed to code)
- [ ] Pre-commit hooks are installed and running
- [ ] Dependencies are regularly audited with `pip-audit`
- [ ] Security scanning is enabled with `bandit`
- [ ] Environment variables are properly configured
- [ ] Django admin is secured with strong credentials
- [ ] HTTPS is enabled in production
- [ ] Database access is restricted
- [ ] Redis is password-protected
