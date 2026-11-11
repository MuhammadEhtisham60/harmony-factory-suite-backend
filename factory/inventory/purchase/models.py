"""
InventoryPurchase and InventoryPurchaseItem models for the Inventory module.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings

from factory.purchase.supplier.models import Supplier
from factory.inventory.item.models import InventoryItem


class InventoryPurchase(models.Model):
    """
    A purchase order for inventory items. Stock is updated when status → Confirmed.
    Also tracks payment settlement (Pending, Partially Paid, Paid).
    """

    class StatusChoices(models.TextChoices):
        DRAFT = "Draft", "Draft"
        CONFIRMED = "Confirmed", "Confirmed"

    class PaymentStatusChoices(models.TextChoices):
        PENDING = "Pending", "Pending"
        PARTIALLY_PAID = "Partially Paid", "Partially Paid"
        PAID = "Paid", "Paid"

    purchase_number = models.CharField(max_length=50, unique=True, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="inventory_purchases",
    )
    purchase_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_purchases",
    )

    class Meta:
        ordering = ["-purchase_date", "-id"]
        verbose_name = "Inventory Purchase"
        verbose_name_plural = "Inventory Purchases"

    def __str__(self):
        return f"{self.purchase_number} - {self.supplier}"

    def recompute_payment_fields(self, explicit_status=None):
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.amount_paid or 0))
        if paid < Decimal("0"):
            paid = Decimal("0")
        if total > Decimal("0") and paid > total:
            paid = total
        due = max(Decimal("0"), total - paid)
        self.amount_paid = paid
        self.amount_due = due

        if explicit_status in dict(self.PaymentStatusChoices.choices):
            self.payment_status = explicit_status
            if explicit_status == self.PaymentStatusChoices.PAID and total > Decimal("0"):
                self.amount_paid = total
                self.amount_due = Decimal("0")
            elif explicit_status == self.PaymentStatusChoices.PENDING:
                self.amount_paid = Decimal("0")
                self.amount_due = total
        else:
            if total > Decimal("0") and due == Decimal("0"):
                self.payment_status = self.PaymentStatusChoices.PAID
            elif paid > Decimal("0") and due > Decimal("0"):
                self.payment_status = self.PaymentStatusChoices.PARTIALLY_PAID
            else:
                self.payment_status = self.PaymentStatusChoices.PENDING

    def save(self, *args, **kwargs):
        if not self.purchase_number:
            last = InventoryPurchase.objects.order_by("-id").first()
            next_number = (last.id + 1) if last else 1
            self.purchase_number = f"INVPO-{next_number:04d}"
        if "update_fields" not in kwargs:
            self.recompute_payment_fields()
        super().save(*args, **kwargs)


class InventoryPurchaseItem(models.Model):
    """
    A line item within an InventoryPurchase.
    """

    purchase = models.ForeignKey(
        InventoryPurchase,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = "Inventory Purchase Item"
        verbose_name_plural = "Inventory Purchase Items"

    def __str__(self):
        return f"{self.purchase.purchase_number} – {self.inventory_item.item_name}"
