from django.db import models

from customers.models import Customer

from ..config import get_config
from ..enums import AccountStatus, AccountType, Channel, Protocol
from .fields import EncryptedCharField

__all__ = ["EmailAccount", "EmailContact"]


class EmailAccount(models.Model):
    name = models.CharField(max_length=200)
    email_address = models.EmailField(unique=True)
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices, default=AccountType.INDIVIDUAL,
    )
    status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.INACTIVE,
    )
    department = models.CharField(max_length=100, blank=True)

    # Channel Configuration
    inbound_channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IMAP,
        help_text="Service for receiving messages",
    )
    outbound_channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.SMTP,
        help_text="Service for sending messages",
    )

    # SMTP Configuration
    smtp_server = models.CharField(max_length=200)
    smtp_port = models.IntegerField(default=get_config("SMTP_DEFAULT_PORT", 587))
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    smtp_username = models.CharField(max_length=200)
    smtp_password = EncryptedCharField(max_length=200)

    # Incoming Email Configuration
    incoming_protocol = models.CharField(
        max_length=10, choices=Protocol.choices, default=Protocol.IMAP,
    )
    incoming_server = models.CharField(max_length=200)
    incoming_port = models.IntegerField(default=get_config("IMAP_DEFAULT_PORT", 993))
    incoming_use_ssl = models.BooleanField(default=True)
    incoming_username = models.CharField(max_length=200)
    incoming_password = EncryptedCharField(max_length=200)

    # Polling Configuration
    poll_frequency = models.IntegerField(
        default=get_config("POLLING_INTERVAL", 300),
        help_text="Polling frequency in seconds",
    )
    max_emails_per_poll = models.IntegerField(
        default=get_config("MAX_MESSAGES_PER_POLL", 50),
    )
    auto_polling_enabled = models.BooleanField(default=True)

    # Status and Metadata
    last_poll_at = models.DateTimeField(null=True, blank=True)
    last_successful_poll_at = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)
    total_emails_received = models.IntegerField(default=0)
    total_emails_sent = models.IntegerField(default=0)

    # Display Information
    display_name = models.CharField(max_length=200, blank=True)
    signature = models.TextField(blank=True)
    footer = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_accounts"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.email_address})"

    @property
    def is_healthy(self):
        return self.status == AccountStatus.ACTIVE and not self.last_error_message

    def get_credentials(self):
        """Get account credentials securely.

        Returns
        -------
            dict: Dictionary with decrypted credentials

        """
        return {
            "smtp": {
                "username": self.smtp_username,
                "password": self.smtp_password,
                "server": self.smtp_server,
                "port": self.smtp_port,
                "use_tls": self.smtp_use_tls,
                "use_ssl": self.smtp_use_ssl,
            },
            "incoming": {
                "username": self.incoming_username,
                "password": self.incoming_password,
                "server": self.incoming_server,
                "port": self.incoming_port,
                "use_ssl": self.incoming_use_ssl,
                "protocol": self.incoming_protocol,
            },
        }


class EmailContact(models.Model):
    account = models.ForeignKey(
        EmailAccount, on_delete=models.CASCADE, related_name="contacts",
    )
    email_address = models.EmailField()
    display_name = models.CharField(max_length=200, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    organization = models.CharField(max_length=200, blank=True)

    # Statistics
    total_emails_received = models.IntegerField(default=0)
    total_emails_sent = models.IntegerField(default=0)
    last_email_at = models.DateTimeField(null=True, blank=True)

    # Customer Linking
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_contacts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_contacts"
        unique_together = ["account", "email_address"]

    def __str__(self):
        return f"{self.display_name or self.email_address}"

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.email_address
