"""
YarnBuyer model for the Yarn module.
"""

from django.db import models
from django.conf import settings


class YarnBuyer(models.Model):
    """
    Represents a buyer/customer for yarn sold from stock.
    Completely separate from the Customer model.
    """

    buyer_name = models.CharField(max_length=255)

    company_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    phone_no = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    email = models.EmailField(
        blank=True,
        default=""
    )

    address = models.TextField(
        blank=True,
        default=""
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        default="Pakistan"
    )

    status = models.CharField(
        max_length=50,
        default="Active"
    )

    notes = models.TextField(
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
        related_name="created_yarn_buyers"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_buyers"
    )

    class Meta:
        ordering = ["buyer_name"]
        verbose_name = "Yarn Buyer"
        verbose_name_plural = "Yarn Buyers"

    def __str__(self):
        return self.buyer_name
