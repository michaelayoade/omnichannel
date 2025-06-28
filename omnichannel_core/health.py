"""Health check endpoints for monitoring the application status."""

import logging
import redis

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def check_database() -> dict[str, bool | str]:
    """Check database connectivity by executing a simple query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return {"status": True, "message": "Database connection successful"}
    except Exception as e:
        logger.error(f"Database health check failed: {e!s}")
        return {"status": False, "message": f"Database error: {e!s}"}


def check_auth() -> dict[str, bool | str]:
    """Check auth system by counting users."""
    try:
        user_count = User.objects.count()
        return {
            "status": True,
            "message": f"Auth system operational, {user_count} users in database",
        }
    except Exception as e:
        logger.error(f"Auth system health check failed: {e!s}")
        return {"status": False, "message": f"Auth system error: {e!s}"}


def check_redis() -> dict[str, bool | str]:
    """Check Redis connectivity."""
    try:
        redis_url = settings.REDIS_URL
        r = redis.from_url(redis_url)
        r.ping()
        return {"status": True, "message": "Redis connection successful"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e!s}")
        return {"status": False, "message": f"Redis error: {e!s}"}


@require_GET
@cache_page(30)  # Cache results for 30 seconds
def health_check(request) -> JsonResponse:
    """Basic health check endpoint that validates core system components.

    Returns HTTP 200 if all systems are operational, HTTP 500 otherwise.
    """
    checks: list[dict[str, bool | str]] = []

    # Add basic checks
    db_check = check_database()
    checks.append({"name": "database", "result": db_check})

    auth_check = check_auth()
    checks.append({"name": "auth", "result": auth_check})
    
    # Add Redis check
    redis_check = check_redis()
    checks.append({"name": "redis", "result": redis_check})

    # Application version
    app_version = getattr(settings, "APP_VERSION", "dev")

    # Compute overall status
    is_healthy = all(check["result"]["status"] for check in checks)

    # Build response
    response_data = {
        "status": "healthy" if is_healthy else "unhealthy",
        "version": app_version,
        "checks": checks,
    }

    status_code = 200 if is_healthy else 500

    return JsonResponse(response_data, status=status_code)


@require_GET
def readiness_check(request) -> JsonResponse:
    """Readiness check endpoint to determine if the app can accept traffic.

    Used by Kubernetes or other orchestration tools to determine if
    the app is ready to receive requests.
    """
    # Check all critical dependencies
    db_check = check_database()
    redis_check = check_redis()
    
    all_services_ready = db_check["status"] and redis_check["status"]

    if all_services_ready:
        return JsonResponse({"status": "ready"})
    else:
        reasons = []
        if not db_check["status"]:
            reasons.append(f"Database: {db_check['message']}")
        if not redis_check["status"]:
            reasons.append(f"Redis: {redis_check['message']}")
            
        return JsonResponse(
            {"status": "not ready", "reasons": reasons},
            status=503,
        )
