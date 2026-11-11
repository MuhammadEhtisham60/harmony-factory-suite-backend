"""
InventoryUnit model for the Inventory module.
"""

from django.db import models


class InventoryUnit(models.Model):
    """
    Unit of measurement for inventory items (e.g., Kg, Litre, Piece).
    """

    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Inventory Unit"
        verbose_name_plural = "Inventory Units"

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
