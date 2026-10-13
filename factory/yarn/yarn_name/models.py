"""
YarnName model for the Yarn module.
"""

from django.db import models
from django.conf import settings


class YarnName(models.Model):
    """
    Represents the name/title of a yarn (e.g. 'Cotton', 'Polyester', 'PC Blend').
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Name of the yarn"
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
        related_name="created_yarn_names"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_names"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Yarn Name"
        verbose_name_plural = "Yarn Names"

    def __str__(self):
        return self.name

    @property
    def yarn_name(self):
        return self.name
