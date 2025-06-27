from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from customers.models import Customer


class SplynxSyncLog(models.Model):
    SYNC_TYPE_CHOICES = [
        ("customers", "Customers"),
        ("services", "Services"),
        ("invoices", "Invoices"),
        ("tickets", "Tickets"),
        ("payments", "Payments"),
    ]

    SYNC_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("partial", "Partial"),
    ]

    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=SYNC_STATUS_CHOICES, default="pending",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    sync_details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "splynx_sync_logs"
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"Splynx {self.get_sync_type_display()} sync - {self.get_status_display()}"
        )


class SplynxCustomerMapping(models.Model):
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="splynx_mapping",
    )
    splynx_customer_id = models.CharField(max_length=100, unique=True)
    splynx_login = models.CharField(max_length=100, blank=True)
    splynx_data = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(max_length=20, default="synced")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "splynx_customer_mappings"

    def __str__(self):
        return f"Splynx mapping for {self.customer.full_name}"


class SplynxServiceMapping(models.Model):
    SERVICE_STATUS_CHOICES = [
        ("active", "Active"),
        ("stopped", "Stopped"),
        ("blocked", "Blocked"),
        ("disabled", "Disabled"),
    ]

    customer_mapping = models.ForeignKey(
        SplynxCustomerMapping, on_delete=models.CASCADE, related_name="services",
    )
    splynx_service_id = models.CharField(max_length=100, unique=True)
    service_name = models.CharField(max_length=200)
    service_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=SERVICE_STATUS_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    splynx_data = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "splynx_service_mappings"

    def __str__(self):
        return (
            f"Splynx service {self.service_name} for "
            f"{self.customer_mapping.customer.full_name}"
        )


class SplynxTicketMapping(models.Model):
    TICKET_STATUS_CHOICES = [
        ("new", "New"),
        ("work_in_progress", "Work in Progress"),
        ("waiting_on_customer", "Waiting on Customer"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    customer_mapping = models.ForeignKey(
        SplynxCustomerMapping, on_delete=models.CASCADE, related_name="tickets",
    )
    splynx_ticket_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=TICKET_STATUS_CHOICES)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="normal",
    )
    category = models.CharField(max_length=100, blank=True)
    assigned_to = models.CharField(max_length=100, blank=True)
    splynx_data = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_conversation = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "splynx_ticket_mappings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Splynx ticket {self.splynx_ticket_id} - {self.title}"


class SplynxInvoiceMapping(models.Model):
    INVOICE_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
        ("partial", "Partial"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    customer_mapping = models.ForeignKey(
        SplynxCustomerMapping, on_delete=models.CASCADE, related_name="invoices",
    )
    splynx_invoice_id = models.CharField(max_length=100, unique=True)
    invoice_number = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    splynx_data = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "splynx_invoice_mappings"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Splynx invoice {self.invoice_number} - "
            f"{self.customer_mapping.customer.full_name}"
        )


class SplynxWebhookEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ("customer.created", "Customer Created"),
        ("customer.updated", "Customer Updated"),
        ("customer.deleted", "Customer Deleted"),
        ("service.created", "Service Created"),
        ("service.updated", "Service Updated"),
        ("service.deleted", "Service Deleted"),
        ("ticket.created", "Ticket Created"),
        ("ticket.updated", "Ticket Updated"),
        ("invoice.created", "Invoice Created"),
        ("invoice.updated", "Invoice Updated"),
        ("payment.created", "Payment Created"),
    ]

    PROCESSING_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
        ("ignored", "Ignored"),
    ]

    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    splynx_object_id = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    processing_status = models.CharField(
        max_length=20, choices=PROCESSING_STATUS_CHOICES, default="pending",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "splynx_webhook_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["processing_status", "created_at"]),
            models.Index(fields=["event_type", "splynx_object_id"]),
        ]

    def __str__(self):
        return f"Splynx webhook {self.event_type} - {self.splynx_object_id}"
