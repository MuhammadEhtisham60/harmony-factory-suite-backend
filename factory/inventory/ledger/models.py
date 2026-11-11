"""
InventoryLedger model for the Inventory module.
"""

from django.db import models
from django.conf import settings

from factory.inventory.item.models import InventoryItem
from factory.purchase.supplier.models import Supplier


class InventoryLedger(models.Model):
    """
    Immutable audit ledger for every stock movement of an inventory item.
    Created automatically by services (never directly by API callers).
    """

    class TransactionTypeChoices(models.TextChoices):
        OPENING_STOCK = "Opening Stock", "Opening Stock"
        STOCK_IN = "Stock In", "Stock In"
        STOCK_OUT = "Stock Out", "Stock Out"
        ADJUSTMENT_IN = "Adjustment In", "Adjustment In"
        ADJUSTMENT_OUT = "Adjustment Out", "Adjustment Out"

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    transaction_date = models.DateField()
    transaction_number = models.CharField(max_length=100)
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionTypeChoices.choices,
    )

    quantity_in = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_out = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    running_balance = models.DecimalField(max_digits=12, decimal_places=4)

    reference_id = models.IntegerField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True, default="")

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_ledger_entries",
    )

    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_ledger_entries",
    )

    class Meta:
        ordering = ["transaction_date", "id"]
        verbose_name = "Inventory Ledger"
        verbose_name_plural = "Inventory Ledger Entries"

    def __str__(self):
        return f"{self.transaction_number} – {self.transaction_type} ({self.inventory_item})"
