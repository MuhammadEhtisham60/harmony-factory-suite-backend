"""
Beam Model for the Factory module.
"""

from django.db import models
from django.conf import settings


class Beam(models.Model):

    class StatusChoices(models.TextChoices):
        AVAILABLE = "Available", "Available"
        SIZING = "Sizing", "Sizing"
        LOADED = "Loaded", "Loaded"
        IN_PRODUCTION = "In Production", "In Production"
        COMPLETED = "Completed", "Completed"
        DAMAGED = "Damaged", "Damaged"
        INACTIVE = "Inactive", "Inactive"

    beam_code = models.CharField(
        max_length=50,
        unique=True
    )

    beam_name = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    beam_number = models.CharField(
        max_length=100,
        unique=True
    )

    yarn_count = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    warp_count = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    total_ends = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    length = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    weight = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    production_order = models.CharField(
        max_length=100,
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
        related_name="created_beams"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_beams"
    )

    class Meta:
        ordering = ["beam_code"]
        verbose_name = "Beam"
        verbose_name_plural = "Beams"

    def __str__(self):
        return f"{self.beam_code} - {self.beam_number}"
