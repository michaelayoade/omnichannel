"""
Custom exceptions for the email integration application.

This module defines a hierarchy of custom exception classes to provide more specific
and actionable error information throughout the email integration components.
"""


class EmailIntegrationError(Exception):
    """Base exception for all errors in the email integration app."""

    pass


class ServiceError(EmailIntegrationError):
    """Base exception for service layer errors."""

    pass


class ValidationError(ServiceError):
    """Raised when data validation fails."""

    pass


class AccountNotFoundError(ServiceError):
    """Raised when an email account is not found."""

    pass


class MessageNotFoundError(ServiceError):
    """Raised when an email message is not found."""

    pass


class SendError(ServiceError):
    """Raised when a message fails to send."""

    pass


class ChannelError(EmailIntegrationError):
    """Base exception for channel-related errors."""

    pass


class AuthenticationError(ChannelError):
    """Raised when authentication with an email server fails."""

    pass


class ConnectionError(ChannelError):
    """Raised for network connection issues with an email server."""

    pass


class PollingError(ChannelError):
    """Raised for errors that occur during the email polling process."""

    pass


class SendingError(ChannelError):
    """Raised for errors that occur during the email sending process."""

    pass


class ConfigurationError(EmailIntegrationError):
    """Raised for invalid or missing configuration."""

    pass
