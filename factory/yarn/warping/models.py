"""
Warping master model for the Yarn module.

A `Warping` is a warping unit / party that yarn can be sent to. Dispatch and
set-return records reuse the shared processing workflow (`YarnOutcome` with
`outcome_type == "Warping"` and `SizingOutcome` for the returned set), see
`factory.yarn.processing`.
"""

from django.conf import settings
from django.db import models


class Warping(models.Model):
    """
    A warping unit or party that receives yarn for the warping process.
    Referenced from YarnOutcome when outcome_type == 'Warping'.
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    warping_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, default="")
    phone_no = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_warpings",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_warpings",
    )

    class Meta:
        ordering = ["warping_name"]
        verbose_name = "Warping"
        verbose_name_plural = "Warpings"

    def __str__(self):
        return self.warping_name
