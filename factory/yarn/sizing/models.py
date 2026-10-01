"""
Sizing model for the Yarn module.
Represents a sizing unit/party that yarn can be sent to.
"""

from django.db import models
from django.conf import settings


class Sizing(models.Model):
    """
    A sizing unit or party that receives yarn for the sizing process.
    Referenced from YarnOutcome when outcome_type == 'Sizing'.
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    sizing_name = models.CharField(max_length=255)

    contact_person = models.CharField(
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

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
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
        related_name="created_sizings"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_sizings"
    )

    class Meta:
        ordering = ["sizing_name"]
        verbose_name = "Sizing"
        verbose_name_plural = "Sizings"

    def __str__(self):
        return self.sizing_name
