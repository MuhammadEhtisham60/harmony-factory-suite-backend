"""
Loom Model for the Factory module.
"""

from django.db import models
from django.conf import settings


class Loom(models.Model):

    class StatusChoices(models.TextChoices):
        AVAILABLE = "Available", "Available"
        INACTIVE = "Inactive", "Inactive"
        SIZING = "Sizing", "Sizing"
        PRODUCTION = "Production", "Production"
        MAINTENANCE = "Maintenance", "Maintenance"
        BREAKDOWN = "Breakdown", "Breakdown"

    # Backward compatibility alias
    StatusChoices.ACTIVE = StatusChoices.AVAILABLE

    loom_code = models.CharField(
        max_length=50,
        unique=True
    )

    loom_name = models.CharField(
        max_length=255
    )

    model_number = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    width = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True
    )

    installation_date = models.DateField(
        null=True,
        blank=True
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    status = models.CharField(
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE
    )

    notes = models.TextField(
        blank=True,
        default=""
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_looms"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_looms"
    )

    class Meta:
        ordering = ["loom_code"]
        verbose_name = "Loom"
        verbose_name_plural = "Looms"
        indexes = [
            models.Index(fields=["status"], name="factory_loom_stat_idx"),
        ]

    def __str__(self):
        return f"{self.loom_code} - {self.loom_name}"
