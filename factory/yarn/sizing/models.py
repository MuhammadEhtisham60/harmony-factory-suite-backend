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


class SizingOutcome(models.Model):
    """
    Represents the return of a Set from Sizing: "What Set came back from Sizing?"
    Maintains all sizing set specifications, yarn usage, and shortage metrics.
    Can be loaded onto multiple existing Beams via BeamLoading.
    """
    sizing = models.ForeignKey(
        Sizing,
        on_delete=models.PROTECT,
        related_name="outcomes"
    )

    outcome_date = models.DateField()

    set_no = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Sizing Set Number"
    )

    sizing_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Name of the Sizing Unit"
    )

    total_bags_on_sizing = models.PositiveIntegerField(
        default=0,
        help_text="Total bags sent/processed on sizing"
    )

    bag_packing_cone = models.PositiveIntegerField(
        default=0,
        help_text="Packing cones per bag"
    )

    total_cones = models.PositiveIntegerField(
        default=0,
        help_text="Total cones on sizing"
    )

    remaining_bags_on_sizing_stock = models.PositiveIntegerField(
        default=0,
        help_text="Remaining bags on sizing stock"
    )

    remaining_cones_on_sizing_stock = models.PositiveIntegerField(
        default=0,
        help_text="Remaining cones on sizing stock"
    )

    lagat_bags = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Lagat in bags"
    )

    lagat_cones = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Lagat in cones"
    )

    brand = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Yarn Brand / Mill"
    )

    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fabric / Reed width in inches"
    )

    set_length_meter = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Set length in meters"
    )

    set_length_gaz = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Set length in gaz (yards)"
    )

    total_tarr = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total ends / Tarr count"
    )

    yarn_beam = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Yarn beam count / identifier"
    )

    back_beam = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Back beam count / identifier"
    )

    count = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Yarn Count (e.g. 20/1, 40/1)"
    )

    total_set_lumbai = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total set length / lumbai"
    )

    total_set_shortage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total set shortage"
    )

    remarks = models.TextField(
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
        related_name="created_sizing_outcomes"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_sizing_outcomes"
    )

    class Meta:
        ordering = ["-outcome_date", "-id"]
        verbose_name = "Sizing Outcome"
        verbose_name_plural = "Sizing Outcomes"

    def __str__(self):
        set_str = f" Set #{self.set_no}" if self.set_no else ""
        return f"Sizing Outcome #{self.id}{set_str} ({self.sizing_name or self.sizing.sizing_name})"

    def save(self, *args, **kwargs):
        if not self.sizing_name and self.sizing_id:
            self.sizing_name = self.sizing.sizing_name
        if not self.total_cones and self.total_bags_on_sizing and self.bag_packing_cone:
            self.total_cones = self.total_bags_on_sizing * self.bag_packing_cone
        super().save(*args, **kwargs)

    @property
    def total_beams(self):
        # Return count of beam assignments or beam loadings
        count = self.beam_assignments.count()
        if count == 0 and hasattr(self, "beam_loadings"):
            return self.beam_loadings.count()
        return count



class SizingBeamAssignment(models.Model):
    """
    Junction and history record connecting an existing Beam to a SizingOutcome.
    Maintains complete audit history of all sizing cycles a physical Beam undergoes.
    A Beam can only have one active (ASSIGNED or IN_USE) assignment at any given time.
    """

    class StatusChoices(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_USE = "IN_USE", "In Use"
        COMPLETED = "COMPLETED", "Completed"
        RELEASED = "RELEASED", "Released"

    sizing_outcome = models.ForeignKey(
        SizingOutcome,
        on_delete=models.PROTECT,
        related_name="beam_assignments"
    )

    beam = models.ForeignKey(
        "factory.Beam",
        on_delete=models.PROTECT,
        related_name="sizing_assignments"
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ASSIGNED
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    released_at = models.DateTimeField(
        null=True,
        blank=True
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
        related_name="created_sizing_beam_assignments"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_sizing_beam_assignments"
    )

    class Meta:
        ordering = ["-assigned_at", "-id"]
        verbose_name = "Sizing Beam Assignment"
        verbose_name_plural = "Sizing Beam Assignments"
        indexes = [
            models.Index(
                fields=["beam", "status"],
                name="factory_sba_beam_stat_idx"
            ),
            models.Index(
                fields=["sizing_outcome", "status"],
                name="factory_sba_so_stat_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["beam"],
                condition=models.Q(status__in=["ASSIGNED", "IN_USE"]),
                name="unique_active_sizing_assignment_per_beam"
            )
        ]

    def __str__(self):
        return f"Assignment #{self.id}: Beam {self.beam_id} -> SizingOutcome #{self.sizing_outcome_id} ({self.status})"

    @property
    def is_active(self):
        return self.status in [self.StatusChoices.ASSIGNED, self.StatusChoices.IN_USE]

