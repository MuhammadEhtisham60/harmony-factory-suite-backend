"""
Customer and CustomerBankAccount models for the Sales module.
"""

from django.db import models
from django.conf import settings


class Customer(models.Model):

    class CustomerType(models.TextChoices):
        WHOLESALER = "Wholesaler", "Wholesaler"
        RETAILER = "Retailer", "Retailer"
        DISTRIBUTOR = "Distributor", "Distributor"
        MANUFACTURER = "Manufacturer", "Manufacturer"
        EXPORTER = "Exporter", "Exporter"
        GENERAL = "General", "General"
        OTHER = "Other", "Other"

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"
        BLOCKED = "Blocked", "Blocked"

    customer_code = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )

    customer_name = models.CharField(
        max_length=255
    )

    company_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    address = models.TextField(
        blank=True,
        default=""
    )

    phone = models.CharField(
        max_length=50
    )

    contact_person = models.CharField(
        max_length=255
    )

    email = models.EmailField(
        blank=True,
        default=""
    )

    customer_type = models.CharField(
        max_length=50,
        choices=CustomerType.choices,
        default=CustomerType.GENERAL
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customers"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_customers"
    )

    class Meta:
        ordering = ["customer_name"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return f"{self.customer_code} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.customer_code:
            last_customer = Customer.objects.order_by("-id").first()

            next_number = (
                last_customer.id + 1
                if last_customer
                else 1
            )

            self.customer_code = f"CUS-{next_number:04d}"

        super().save(*args, **kwargs)


class CustomerBankAccount(models.Model):
    """
    Bank account details belonging to a Customer.
    Multiple accounts are allowed; only one can be marked primary.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="bank_accounts"
    )

    bank_name = models.CharField(
        max_length=255
    )

    account_title = models.CharField(
        max_length=255
    )

    account_number = models.CharField(
        max_length=100
    )

    iban = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    branch_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    branch_code = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    swift_code = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    is_primary = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-is_primary", "bank_name"]
        verbose_name = "Customer Bank Account"
        verbose_name_plural = "Customer Bank Accounts"

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

    def save(self, *args, **kwargs):
        """
        Ensure only one bank account per customer is flagged as primary.
        When this account is set primary, demote all other accounts first.
        """
        if self.is_primary:
            CustomerBankAccount.objects.filter(
                customer=self.customer,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
