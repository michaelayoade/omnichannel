"""Monitoring utilities for email integration.

This module provides tools for application monitoring, error reporting,
and observability using services like Sentry.
"""

import functools
import inspect
import os

from django.conf import settings

from omnichannel_core.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def setup_sentry():
    """Configure Sentry for error reporting if available.

    This should be called during Django initialization to set up
    error monitoring with proper configuration.
    """
    # Get Sentry DSN from environment or settings
    dsn = os.environ.get("SENTRY_DSN") or getattr(settings, "SENTRY_DSN", None)

    if not dsn:
        logger.info("Sentry integration not configured - skipping setup")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        # Configure Sentry with appropriate integrations
        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                DjangoIntegration(),
                CeleryIntegration(),
            ],
            # Set environment explicitly
            environment=os.environ.get("DEPLOYMENT_ENVIRONMENT", "development"),
            # Set traces sample rate from config, or use more conservative default
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
            # Only send errors in production by default
            send_default_pii=os.environ.get("SENTRY_SEND_PII", "false").lower()
            == "true",
        )

        # Log success
        logger.info("Sentry integration configured successfully")
        return True

    except ImportError:
        logger.warning("Sentry SDK not installed - error reporting disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to configure Sentry: {e!s}")
        return False


def capture_exception(func=None, *, tags=None, level="error"):
    """Decorator to capture exceptions with Sentry and proper context.

    Args:
    ----
        func: The function to wrap
        tags: Dictionary of tags to add to the error
        level: Error level (error, warning)

    Returns:
    -------
        Wrapped function that reports exceptions to Sentry

    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # Log the exception with structured context
                context = {}

                # Add function details
                context["function"] = f.__qualname__
                context["module"] = f.__module__

                # Add request ID if present in args
                request_id = None

                # Try to find request_id in kwargs
                if "_request_id" in kwargs:
                    request_id = kwargs["_request_id"]

                # If not found in kwargs, try to find it in args that are request objs
                if not request_id:
                    for arg in args:
                        if hasattr(arg, "request_id"):
                            request_id = arg.request_id
                            break

                if request_id:
                    context["request_id"] = request_id

                # Add custom tags
                if tags:
                    context.update(tags)

                # Log with appropriate level
                if level == "error":
                    logger.error(
                        f"Exception in {f.__qualname__}: {e!s}", extra=context,
                    )
                else:
                    logger.warning(
                        f"Exception in {f.__qualname__}: {e!s}", extra=context,
                    )

                # Report to Sentry if available
                try:
                    import sentry_sdk

                    with sentry_sdk.push_scope() as scope:
                        # Add context to Sentry scope
                        for key, value in context.items():
                            scope.set_tag(key, value)

                        # Add function arguments if not sensitive
                        # (Be careful with this in production - could expose sensitive data)
                        if getattr(settings, "DEBUG", False):
                            arg_spec = inspect.getfullargspec(f)
                            arg_names = arg_spec.args

                            # Skip 'self' for methods
                            if arg_names and arg_names[0] == "self":
                                arg_names = arg_names[1:]

                            # Add arguments to context
                            for i, arg_name in enumerate(arg_names):
                                if i < len(args):
                                    # Skip password or sensitive fields
                                    if arg_name.lower() not in (
                                        "password",
                                        "token",
                                        "secret",
                                        "key",
                                    ):
                                        scope.set_context(
                                            f"arg:{arg_name}", repr(args[i]),
                                        )

                        # Capture the exception
                        sentry_sdk.capture_exception(e)
                except ImportError:
                    pass

                # Re-raise the exception
                raise

        return wrapper

    # Handle usage without arguments
    if func:
        return decorator(func)
    return decorator
