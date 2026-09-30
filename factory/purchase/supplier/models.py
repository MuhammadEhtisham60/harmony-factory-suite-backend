"""
Supplier and SupplierBankAccount models for the Purchase module.
"""

from django.db import models
from django.conf import settings


class Supplier(models.Model):

    class SupplierType(models.TextChoices):
        YARN = "Yarn", "Yarn"
        SPARE_PARTS = "Spare Parts", "Spare Parts"
        MACHINERY = "Machinery", "Machinery"
        DYES_CHEMICALS = "Dyes & Chemicals", "Dyes & Chemicals"
        PACKAGING = "Packaging", "Packaging"
        GENERAL = "General", "General"
        OTHER = "Other", "Other"

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"
        BLOCKED = "Blocked", "Blocked"

    supplier_code = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )

    supplier_name = models.CharField(max_length=255)

    company_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    address = models.TextField(
        blank=True,
        default=""
    )

    phone = models.CharField(max_length=50)

    contact_person = models.CharField(
        max_length=255
    )

    email = models.EmailField(
        blank=True,
        default=""
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )

    supplier_type = models.CharField(
        max_length=50,
        choices=SupplierType.choices,
        default=SupplierType.GENERAL
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_suppliers"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_suppliers"
    )

    class Meta:
        ordering = ["supplier_name"]
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return f"{self.supplier_code} - {self.supplier_name}"

    def save(self, *args, **kwargs):
        if not self.supplier_code:
            last_supplier = Supplier.objects.order_by("-id").first()

            next_number = (
                last_supplier.id + 1
                if last_supplier
                else 1
            )

            self.supplier_code = f"SUP-{next_number:04d}"

        super().save(*args, **kwargs)


class SupplierBankAccount(models.Model):
    """
    Bank account details belonging to a Supplier.
    Multiple accounts are allowed; only one can be marked primary.
    """

    supplier = models.ForeignKey(
        Supplier,
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
        verbose_name = "Supplier Bank Account"
        verbose_name_plural = "Supplier Bank Accounts"

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

    def save(self, *args, **kwargs):
        """
        Ensure only one bank account per supplier is flagged as primary.
        If this account is set as primary, demote all other accounts of the
        same supplier first.
        """
        if self.is_primary:
            SupplierBankAccount.objects.filter(
                supplier=self.supplier,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
