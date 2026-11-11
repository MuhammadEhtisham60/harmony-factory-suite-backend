"""
InventoryTransaction model for the Inventory module.
"""

from django.db import models
from django.conf import settings

from factory.inventory.item.models import InventoryItem


class InventoryTransaction(models.Model):
    """
    A stock movement (out / adjustment) against an inventory item.
    Stock and ledger are updated immediately on creation.
    """

    class TransactionTypeChoices(models.TextChoices):
        STOCK_OUT = "Stock Out", "Stock Out"
        ADJUSTMENT_IN = "Adjustment In", "Adjustment In"
        ADJUSTMENT_OUT = "Adjustment Out", "Adjustment Out"

    transaction_number = models.CharField(max_length=50, unique=True, editable=False)
    transaction_date = models.DateField()

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionTypeChoices.choices,
    )

    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    notes = models.TextField(blank=True, default="")
    issued_to = models.CharField(max_length=255, blank=True, default="")
    related_area = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_transactions",
    )

    class Meta:
        ordering = ["-transaction_date", "-id"]
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"

    def __str__(self):
        return f"{self.transaction_number} – {self.transaction_type}"

    def save(self, *args, **kwargs):
        if not self.transaction_number:
            last = InventoryTransaction.objects.order_by("-id").first()
            next_number = (last.id + 1) if last else 1
            self.transaction_number = f"INVT-{next_number:04d}"
        super().save(*args, **kwargs)
