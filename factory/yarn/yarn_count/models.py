"""
YarnCount model for the Yarn module.
"""

from django.db import models
from django.conf import settings


class YarnCount(models.Model):
    """
    Represents the yarn count / linear density (e.g. '20s', '40s/2', '16s / 1').
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Yarn count (e.g. '20s', '40s/2', '16s / 1')"
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
        related_name="created_yarn_counts"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_counts"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Yarn Count"
        verbose_name_plural = "Yarn Counts"

    def __str__(self):
        return self.name

    @property
    def yarn_count(self):
        return self.name
