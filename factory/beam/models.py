"""
Beam Model for the Factory module.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver


class Beam(models.Model):

    class StatusChoices(models.TextChoices):
        AVAILABLE = "Available", "Available"
        SIZING = "Sizing", "Sizing"
        WARPING = "Warping", "Warping"
        LOADED = "Loaded", "Loaded"
        IN_PRODUCTION = "In Production", "In Production"
        COMPLETED = "Completed", "Completed"
        DAMAGED = "Damaged", "Damaged"
        INACTIVE = "Inactive", "Inactive"

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
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True
    )

    width = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Beam / fabric width in inches"
    )

    weight = models.DecimalField(
        max_digits=15,
        decimal_places=6,
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

    dispatched_yarn_outcome = models.ForeignKey(
        "factory.YarnOutcome",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatched_beams",
        help_text="Yarn outcome (sizing dispatch) this beam is currently out at sizing for"
    )

    class Meta:
        ordering = ["beam_number"]
        verbose_name = "Beam"
        verbose_name_plural = "Beams"

    def __str__(self):
        return f"{self.beam_number} - {self.beam_name}" if self.beam_name else self.beam_number


class BeamLoading(models.Model):
    """
    Loading the returned Sizing Set onto an existing physical Beam
    and installing that Beam onto a Loom.

    Maintains complete audit history of all sizing sets and looms
    each physical Beam is installed on over its lifecycle.
    """

    class StatusChoices(models.TextChoices):
        LOADED = "Loaded", "Loaded"
        IN_PRODUCTION = "In Production", "In Production"
        COMPLETED = "Completed", "Completed"
        EMPTY = "Empty", "Empty"

    sizing_outcome = models.ForeignKey(
        "factory.SizingOutcome",
        on_delete=models.PROTECT,
        related_name="beam_loadings"
    )

    beam = models.ForeignKey(
        "factory.Beam",
        on_delete=models.PROTECT,
        related_name="loadings"
    )

    loom = models.ForeignKey(
        "factory.Loom",
        on_delete=models.PROTECT,
        related_name="beam_loadings"
    )

    cloth_name = models.ForeignKey(
        "factory.ClothName",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beam_loadings",
        help_text="Master cloth quality reference"
    )

    shortage = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Expected / observed shortage"
    )

    lakhai = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Lakhai (drawing-in / drafting cost or measurement)"
    )

    @property
    def warp_count(self):
        return self.cloth_name.warp_count if self.cloth_name else ""

    @property
    def weft_count(self):
        return self.cloth_name.weft_count if self.cloth_name else ""

    @property
    def cloth_quality(self):
        return self.cloth_name.name if self.cloth_name else ""

    @property
    def reed_width(self):
        return self.cloth_name.reed_width if self.cloth_name else None

    @property
    def reed_count(self):
        return self.cloth_name.reed_count if self.cloth_name else None

    @property
    def pick_count(self):
        return self.cloth_name.pick_count if self.cloth_name else None

    @property
    def pick(self):
        return self.pick_count

    @property
    def width(self):
        return self.reed_width

    installation_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date beam was installed on loom"
    )

    status = models.CharField(
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.LOADED
    )

    expected_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Expected woven cloth length in meters"
    )

    dismount_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date beam was dismounted from loom"
    )

    dismounted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismounted_beam_loadings",
        help_text="User who dismounted the beam"
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
        related_name="created_beam_loadings"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_beam_loadings"
    )

    class Meta:
        ordering = ["-installation_date", "-id"]
        verbose_name = "Beam Loading"
        verbose_name_plural = "Beam Loadings"
        indexes = [
            models.Index(fields=["beam", "status"], name="factory_bl_beam_stat_idx"),
            models.Index(fields=["loom", "status"], name="factory_bl_loom_stat_idx"),
            models.Index(fields=["sizing_outcome", "status"], name="factory_bl_so_stat_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["beam"],
                condition=models.Q(status__in=["Loaded", "In Production"]),
                name="unique_active_loading_per_beam"
            ),
            models.UniqueConstraint(
                fields=["loom"],
                condition=models.Q(status__in=["Loaded", "In Production"]),
                name="unique_active_loading_per_loom"
            ),
        ]

    def __str__(self):
        return f"BeamLoading #{self.id}: Beam {self.beam_id} on Loom {self.loom_id} (Outcome #{self.sizing_outcome_id})"


class Production(models.Model):
    """
    Records cloth/fabric production built from a loaded Beam on a Loom.
    Beam and Loom are derived from the associated BeamLoading record.
    """
    beam_loading = models.ForeignKey(
        BeamLoading,
        on_delete=models.PROTECT,
        related_name="productions"
    )

    production_date = models.DateField(
        help_text="Date of production entry"
    )

    shift = models.CharField(
        max_length=50,
        blank=True,
        default="General",
        help_text="Production shift (e.g. Morning, Night, General)"
    )

    meters_produced = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=0,
        help_text="Fabric length produced in meters"
    )

    operator_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Loom master / weaver operator name"
    )

    remarks = models.TextField(
        blank=True,
        default=""
    )

    beam_emptied = models.BooleanField(
        default=False,
        help_text="Set to True when the physical beam is finished/empty"
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
        related_name="created_productions"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_productions"
    )

    @property
    def beam(self):
        return self.beam_loading.beam if self.beam_loading else None

    @property
    def loom(self):
        return self.beam_loading.loom if self.beam_loading else None

    class Meta:
        ordering = ["-production_date", "-id"]
        verbose_name = "Production"
        verbose_name_plural = "Productions"

    def __str__(self):
        loom_code = self.loom.loom_code if self.loom else "N/A"
        beam_no = self.beam.beam_number if self.beam else "N/A"
        return f"Production #{self.id}: Loom {loom_code} / Beam {beam_no} ({self.meters_produced}m)"


class BeamDismountReconciliation(models.Model):
    """
    Authoritative reconciliation of expected vs. actual cloth production
    when a physical Beam is dismounted from a Loom at the end of its loading cycle.
    """
    beam_loading = models.OneToOneField(
        BeamLoading,
        on_delete=models.PROTECT,
        related_name="reconciliation"
    )

    expected_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Expected woven cloth production length in meters"
    )

    actual_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Actual woven cloth production length in meters (sum of ClothPatch.productive_length)"
    )

    difference = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="difference = actual_length - expected_length (+ exceeds, - below, 0 equal)"
    )

    production_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Production percentage: (actual_length / expected_length) * 100"
    )

    dismount_date = models.DateField(
        help_text="Date beam was dismounted and reconciled"
    )

    dismounted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beam_reconciliations",
        help_text="User who performed the dismount"
    )

    remarks = models.TextField(
        blank=True,
        default="",
        help_text="Reconciliation remarks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-dismount_date", "-id"]
        verbose_name = "Beam Dismount Reconciliation"
        verbose_name_plural = "Beam Dismount Reconciliations"

    def __str__(self):
        return f"Reconciliation for Loading #{self.beam_loading_id}: Actual {self.actual_length}m / Expected {self.expected_length}m"


@receiver(pre_delete, sender="factory.YarnOutcome")
def reset_dispatched_beams_on_yarn_outcome_delete(sender, instance, **kwargs):
    """
    When a yarn outcome (sizing/warping dispatch) is deleted, every beam that
    was dispatched under it and is still waiting at the mill goes back to
    Available. Beams in any other status (e.g. Damaged) are left untouched.
    """
    Beam.objects.filter(
        dispatched_yarn_outcome_id=instance.pk,
        status__in=[Beam.StatusChoices.SIZING, Beam.StatusChoices.WARPING],
    ).update(
        status=Beam.StatusChoices.AVAILABLE,
        dispatched_yarn_outcome=None,
    )


