"""
YarnType model for the Yarn module.
"""

from django.db import models
from django.conf import settings


class YarnType(models.Model):
    """
    Represents the type/composition of a yarn (e.g. 'Carded', 'Combed', 'Ring Spun').
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Type/classification of the yarn"
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description or remarks"
    )

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_yarn_types"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_types"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Yarn Type"
        verbose_name_plural = "Yarn Types"

    def __str__(self):
        return self.name

    @property
    def yarn_type(self):
        return self.name
