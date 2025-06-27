"""Logging utilities for consistent, context-rich logs across the system."""

import logging
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

# Type variable for decorator pattern
F = TypeVar("F", bound=Callable[..., Any])


class ContextLogger:
    """Enhanced logger that automatically includes context data in all log entries.

    Usage:
        logger = ContextLogger(__name__)
        logger.set_context(request_id='123', account_id=456)
        logger.info("Processing started")  # Will include the context automatically

        # To add one-time context for a specific log:
        logger.info("Special operation", extra_context={'operation_id': 789})
    """

    def __init__(self, name: str):
        """Initialize with a standard logger name."""
        self.logger = logging.getLogger(name)
        self.context: dict[str, Any] = {}

    def set_context(self, **kwargs) -> None:
        """Set persistent context data for all subsequent log calls."""
        self.context.update(kwargs)

    def clear_context(self, *keys) -> None:
        """Clear specific keys from context, or all if no keys specified."""
        if not keys:
            self.context.clear()
        else:
            for key in keys:
                if key in self.context:
                    del self.context[key]

    def _log(
        self,
        level: int,
        msg: str,
        *args,
        extra_context: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Internal method to enrich logs with context."""
        # Combine base context with any call-specific extra context
        log_context = self.context.copy()
        if extra_context:
            log_context.update(extra_context)

        # Add context to the 'extra' kwarg expected by the standard logger
        kwargs["extra"] = {**(kwargs.get("extra", {})), "context": log_context}

        self.logger.log(level, msg, *args, **kwargs)

    def debug(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log a debug message with context."""
        self._log(logging.DEBUG, msg, *args, extra_context=extra_context, **kwargs)

    def info(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log an info message with context."""
        self._log(logging.INFO, msg, *args, extra_context=extra_context, **kwargs)

    def warning(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log a warning message with context."""
        self._log(logging.WARNING, msg, *args, extra_context=extra_context, **kwargs)

    def error(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log an error message with context."""
        self._log(logging.ERROR, msg, *args, extra_context=extra_context, **kwargs)

    def exception(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log an exception message with context."""
        self._log(
            logging.ERROR,
            msg,
            *args,
            extra_context=extra_context,
            exc_info=True,
            **kwargs,
        )

    def critical(
        self, msg: str, *args, extra_context: dict[str, Any] | None = None, **kwargs,
    ) -> None:
        """Log a critical message with context."""
        self._log(logging.CRITICAL, msg, *args, extra_context=extra_context, **kwargs)


def with_request_id(func: F) -> F:
    """Decorator to add a unique request_id to the function's logger context.

    Usage:
        @with_request_id
        def my_view(request):
            logger = ContextLogger(__name__)
            logger.info("Processing request")  # Will include request_id
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Generate a unique ID for this request/task execution
        request_id = str(uuid.uuid4())

        # Execute the function with the request_id available
        kwargs["_request_id"] = request_id
        return func(*args, **kwargs)

    return cast(F, wrapper)
