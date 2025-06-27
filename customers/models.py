from django.contrib.auth.models import User
from django.db import models


class Customer(models.Model):
    CUSTOMER_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
        ("blocked", "Blocked"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    splynx_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    customer_id = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=CUSTOMER_STATUS_CHOICES, default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customers"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.customer_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class CustomerService(models.Model):
    SERVICE_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("blocked", "Blocked"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="services"
    )
    splynx_service_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    service_name = models.CharField(max_length=200)
    service_type = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=SERVICE_STATUS_CHOICES, default="active"
    )
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_services"

    def __str__(self):
        return f"{self.customer.full_name} - {self.service_name}"
