"""Test-specific settings configuration."""

import tempfile

from .base import *

# Use in-memory SQLite for testing speed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use console email backend for testing
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use in-memory cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable whitenoise in tests
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Use in-memory channel layer for testing to avoid Redis dependency
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Disable CSRF in tests
CSRF_MIDDLEWARE = "django.middleware.csrf.CsrfViewMiddleware"
MIDDLEWARE = [m for m in MIDDLEWARE if m != CSRF_MIDDLEWARE]

# Keep media in memory during tests
MEDIA_ROOT = tempfile.mkdtemp()

# Turn off the Debug Toolbar in tests
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: False,
}

# Log to console only during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "level": "ERROR",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}
