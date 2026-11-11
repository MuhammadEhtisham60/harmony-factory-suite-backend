"""
InventoryCategory model for the Inventory module.
"""

from django.db import models
from django.conf import settings


class InventoryCategory(models.Model):
    """
    Category for inventory items (e.g., Spare Parts, Chemicals, Stationery).
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_categories",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Inventory Category"
        verbose_name_plural = "Inventory Categories"

    def __str__(self):
        return self.name
