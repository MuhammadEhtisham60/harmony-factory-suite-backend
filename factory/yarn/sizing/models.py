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
        if hasattr(self, "beam_loadings") and self.beam_loadings.exists():
            return self.beam_loadings.count()
        if self.sizing_id:
            from factory.beam.models import Beam
            count = Beam.objects.filter(sizing_assignments__yarn_outcome__sizing_id=self.sizing_id).distinct().count()
            if count > 0:
                return count
        return 0



class SizingBeamAssignment(models.Model):
    """
    Junction and history record connecting an existing Beam to a YarnOutcome.
    Maintains complete audit history of all sizing cycles a physical Beam undergoes.
    A Beam can only have one active (ASSIGNED or IN_USE) assignment at any given time.
    """

    class StatusChoices(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_USE = "IN_USE", "In Use"
        COMPLETED = "COMPLETED", "Completed"
        RELEASED = "RELEASED", "Released"

    yarn_outcome = models.ForeignKey(
        "factory.YarnOutcome",
        on_delete=models.PROTECT,
        related_name="beam_assignments"
    )

    beam = models.ManyToManyField(
        "factory.Beam",
        blank=True,
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
                fields=["yarn_outcome", "status"],
                name="factory_sba_yo_stat_idx"
            ),
        ]

    def __init__(self, *args, **kwargs):
        self._initial_beams = kwargs.pop("beam", None)
        if self._initial_beams is None:
            self._initial_beams = kwargs.pop("beams", None)
        sizing_outcome = kwargs.pop("sizing_outcome", None)
        if sizing_outcome and "yarn_outcome" not in kwargs:
            yo = getattr(sizing_outcome, "yarn_outcome", None)
            if not yo and hasattr(sizing_outcome, "sizing") and sizing_outcome.sizing:
                yo = sizing_outcome.sizing.yarn_outcomes.filter(outcome_type="Sizing").first()
                if not yo:
                    from django.utils import timezone
                    from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome
                    intake = YarnIntake.objects.first()
                    if intake:
                        yo = YarnOutcome.objects.create(
                            yarn_intake=intake,
                            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                            sizing=sizing_outcome.sizing,
                            outcome_bags=0,
                            outcome_weight_per_bag_kg=0,
                            outcome_date=getattr(sizing_outcome, "outcome_date", None) or timezone.now().date(),
                        )
            kwargs["yarn_outcome"] = yo
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if hasattr(self, "_initial_beams") and self._initial_beams is not None:
            beams_to_add = self._initial_beams
            if not hasattr(beams_to_add, "__iter__") or isinstance(beams_to_add, (str, bytes)):
                beams_to_add = [beams_to_add]
            # If active status, verify none of the beams are already in an active assignment
            if self.status in [self.StatusChoices.ASSIGNED, self.StatusChoices.IN_USE]:
                for b in beams_to_add:
                    b_id = getattr(b, "id", b)
                    if b_id:
                        already_active = SizingBeamAssignment.objects.filter(
                            beam__id=b_id,
                            status__in=[self.StatusChoices.ASSIGNED, self.StatusChoices.IN_USE],
                        ).exclude(id=self.id).exists()
                        if already_active:
                            from django.db import IntegrityError
                            raise IntegrityError(f"Beam {b_id} is already in an active sizing assignment.")
            self.beam.set(beams_to_add)
            self._initial_beams = None

    def __str__(self):
        b_count = self.beam.count() if self.id else 0
        return f"Assignment #{self.id}: {b_count} beam(s) -> YarnOutcome #{self.yarn_outcome_id} ({self.status})"

    @property
    def beams(self):
        return self.beam

    @property
    def beam_id(self):
        first_b = self.beam.first() if self.id else None
        return first_b.id if first_b else None

    @property
    def beam_ids(self):
        return list(self.beam.values_list("id", flat=True)) if self.id else []

    @property
    def is_active(self):
        return self.status in [self.StatusChoices.ASSIGNED, self.StatusChoices.IN_USE]

    @property
    def sizing_outcome(self):
        if self.yarn_outcome and self.yarn_outcome.sizing:
            return self.yarn_outcome.sizing.outcomes.first()
        return None

    @property
    def sizing_outcome_id(self):
        so = self.sizing_outcome
        return so.id if so else None


