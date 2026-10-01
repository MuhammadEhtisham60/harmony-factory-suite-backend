"""
YarnIntake and YarnOutcome models for the Yarn module.

Calculation rules (all Decimal, never float):
  LB_PER_KG = Decimal("2.20462262")

  YarnIntake:
    total_cones       = bags * cones_per_bag
    total_rate        = bags * rate_per_bag
    net_weight_kg     = bags * weight_per_bag_kg
    net_weight_lb     = net_weight_kg * LB_PER_KG

    On create:
      remaining_bags       = bags
      remaining_weight_kg  = net_weight_kg
      remaining_weight_lb  = net_weight_lb

  YarnOutcome:
    outcome_weight_kg = outcome_bags * outcome_weight_per_bag_kg
    outcome_weight_lb = outcome_weight_kg * LB_PER_KG

  YarnIntake summary (recalculated from actual outcomes after every mutation):
    outcome_bags        = Sum(outcome.outcome_bags)
    outcome_weight_kg   = Sum(outcome.outcome_weight_kg)
    outcome_weight_lb   = Sum(outcome.outcome_weight_lb)
    remaining_bags      = bags - outcome_bags
    remaining_weight_kg = net_weight_kg - outcome_weight_kg
    remaining_weight_lb = net_weight_lb - outcome_weight_lb
"""

from decimal import Decimal

from django.db import models
from django.conf import settings

from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.purchase.supplier.models import Supplier
from factory.yarn.sizing.models import Sizing

LB_PER_KG = Decimal("2.20462262")


class YarnIntake(models.Model):
    """
    Records a batch of yarn received from a supplier.

    Source-input fields (frontend-provided):
        bags, cones_per_bag, rate_per_bag, weight_per_bag_kg

    Backend-calculated (read-only from API perspective):
        total_cones, total_rate, net_weight_kg, net_weight_lb

    Denormalized summary (recalculated from YarnOutcome records after every mutation):
        outcome_bags, outcome_weight_kg, outcome_weight_lb
        remaining_bags, remaining_weight_kg, remaining_weight_lb
    """

    yarn_name = models.CharField(max_length=255)
    yarn_type = models.CharField(max_length=100)
    yarn_count = models.CharField(max_length=100)

    set_no = models.CharField(
        max_length=100,
        help_text="Manually entered set number. Not auto-generated."
    )

    intake_date = models.DateField()

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="yarn_intakes"
    )

    production_type = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    # ── Source inputs ──────────────────────────────────────────────────────
    bags = models.PositiveIntegerField(default=0)
    cones_per_bag = models.PositiveIntegerField(default=0)
    rate_per_bag = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    weight_per_bag_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # ── Backend-calculated intake totals ───────────────────────────────────
    total_cones = models.PositiveIntegerField(default=0)
    total_rate = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_weight_kg = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    net_weight_lb = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # ── Denormalized outcome summary (recalculated from YarnOutcome) ───────
    outcome_bags = models.PositiveIntegerField(default=0)
    outcome_weight_kg = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    outcome_weight_lb = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # ── Remaining stock (recalculated from YarnOutcome) ────────────────────
    remaining_bags = models.PositiveIntegerField(default=0)
    remaining_weight_kg = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    remaining_weight_lb = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # ── Audit ──────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_yarn_intakes"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_intakes"
    )

    class Meta:
        ordering = ["-intake_date", "-id"]
        verbose_name = "Yarn Intake"
        verbose_name_plural = "Yarn Intakes"

    def __str__(self):
        return f"{self.yarn_name} - {self.set_no}"

    def calculate_intake_fields(self):
        """
        Recalculate all derived intake fields from source inputs.
        Call before saving a new or updated YarnIntake.
        """
        bags = Decimal(str(self.bags))
        cones_per_bag = Decimal(str(self.cones_per_bag))
        rate_per_bag = Decimal(str(self.rate_per_bag))
        weight_per_bag_kg = Decimal(str(self.weight_per_bag_kg))

        self.total_cones = int(bags * cones_per_bag)
        self.total_rate = bags * rate_per_bag
        self.net_weight_kg = bags * weight_per_bag_kg
        self.net_weight_lb = self.net_weight_kg * LB_PER_KG

    def init_remaining_stock(self):
        """
        Initialise remaining stock on first creation (no outcomes yet).
        """
        self.remaining_bags = self.bags
        self.remaining_weight_kg = self.net_weight_kg
        self.remaining_weight_lb = self.net_weight_lb
        self.outcome_bags = 0
        self.outcome_weight_kg = Decimal("0")
        self.outcome_weight_lb = Decimal("0")


class YarnOutcome(models.Model):
    """
    Records yarn dispatched from a YarnIntake batch.

    Rules:
      Sizing:
        yarn_buyer  must be None
        total_price must be 0
        sizing       optional (FK to Sizing)

      Weft:
        yarn_buyer  must be None
        total_price must be 0
        sizing       must be None

      Sold:
        yarn_buyer  required
        total_price must be > 0
        sizing       must be None

    outcome_weight_kg = outcome_bags * outcome_weight_per_bag_kg
    outcome_weight_lb = outcome_weight_kg * LB_PER_KG

    After every CREATE / UPDATE / DELETE the parent YarnIntake summary
    is recalculated from the actual YarnOutcome rows.
    """

    class OutcomeTypeChoices(models.TextChoices):
        SIZING = "Sizing", "Sizing"
        WEFT = "Weft", "Weft"
        SOLD = "Sold", "Sold"

    yarn_intake = models.ForeignKey(
        YarnIntake,
        on_delete=models.CASCADE,
        related_name="outcomes"
    )

    outcome_type = models.CharField(
        max_length=20,
        choices=OutcomeTypeChoices.choices,
        default=OutcomeTypeChoices.SIZING
    )

    outcome_bags = models.PositiveIntegerField(default=0)
    outcome_cones_per_bag = models.PositiveIntegerField(default=0)

    outcome_weight_per_bag_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    # Backend-calculated
    outcome_weight_kg = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    outcome_weight_lb = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    yarn_buyer = models.ForeignKey(
        YarnBuyer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yarn_outcomes"
    )

    sizing = models.ForeignKey(
        Sizing,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yarn_outcomes"
    )

    total_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    outcome_date = models.DateField()

    notes = models.TextField(blank=True, default="")

    # ── Audit ──────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_yarn_outcomes"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_outcomes"
    )

    class Meta:
        ordering = ["-outcome_date", "-id"]
        verbose_name = "Yarn Outcome"
        verbose_name_plural = "Yarn Outcomes"

    def __str__(self):
        return (
            f"{self.yarn_intake.yarn_name} - "
            f"{self.outcome_type} - "
            f"{self.outcome_bags} bags"
        )

    def calculate_outcome_fields(self):
        """
        Recalculate backend-derived outcome weight fields.
        Call before saving.
        """
        outcome_bags = Decimal(str(self.outcome_bags))
        weight_per_bag = Decimal(str(self.outcome_weight_per_bag_kg))
        self.outcome_weight_kg = outcome_bags * weight_per_bag
        self.outcome_weight_lb = self.outcome_weight_kg * LB_PER_KG
