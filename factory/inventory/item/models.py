"""
InventoryItem model for the Inventory module.
"""

from django.db import models
from django.conf import settings

from factory.inventory.category.models import InventoryCategory
from factory.inventory.unit.models import InventoryUnit
from factory.purchase.supplier.models import Supplier


class InventoryItem(models.Model):
    """
    A single inventory item tracked in the system.
    stock is updated via purchases and transactions.
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    item_name = models.CharField(max_length=255)
    item_code = models.CharField(max_length=50, unique=True, editable=False)

    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.PROTECT,
        related_name="items",
    )
    unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.PROTECT,
        related_name="items",
    )

    description = models.TextField(blank=True, default="")
    storage_location = models.CharField(max_length=255, blank=True, default="")

    opening_stock = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    minimum_stock_level = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    current_stock = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    preferred_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preferred_inventory_items",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_items",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_inventory_items",
    )

    class Meta:
        ordering = ["item_name"]
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"

    def save(self, *args, **kwargs):
        if not self.item_code:
            last = InventoryItem.objects.order_by("-id").first()
            next_number = (last.id + 1) if last else 1
            self.item_code = f"INV-{next_number:04d}"
        super().save(*args, **kwargs)
