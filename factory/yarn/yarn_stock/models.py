"""
YarnStock model representing a shared inventory pool.

Multiple YarnIntake deliveries contribute to the same YarnStock pool
when their stock-identifying fields match:
    (yarn_name, yarn_type, yarn_count, production_type)

Dispatches (YarnOutcome) deduct from this shared YarnStock pool rather than
against any specific YarnIntake record.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings

LB_PER_KG = Decimal("2.20462262")


class YarnStock(models.Model):
    """
    Shared yarn inventory pool.

    Stock-identifying attributes (uniqueness constraint):
        yarn_name, yarn_type, yarn_count, production_type

    Inventory fields (current available balances):
        total_boxes:     current available boxes / bags
        cones:           current available cones
        total_weight_kg: current available weight in kilograms
        total_weight_lb: current available weight in pounds
        price:           weighted average intake price per box/bag (Decimal)
    """

    yarn_name = models.CharField(max_length=255)
    yarn_type = models.CharField(max_length=100)
    yarn_count = models.CharField(max_length=100)
    production_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Production category such as Warp, Weft, etc."
    )

    # ── Current Available Balances ─────────────────────────────────────────
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weighted average purchase rate per box/bag from contributing intakes."
    )
    total_boxes = models.IntegerField(
        default=0,
        help_text="Current available boxes / bags remaining in stock."
    )
    cones = models.IntegerField(
        default=0,
        help_text="Current available cones remaining in stock."
    )
    total_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Current available weight in kilograms."
    )
    total_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Current available weight in pounds."
    )

    # ── Audit ──────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_yarn_stocks"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_yarn_stocks"
    )

    class Meta:
        ordering = ["yarn_name", "yarn_count", "production_type", "-id"]
        verbose_name = "Yarn Stock"
        verbose_name_plural = "Yarn Stocks"
        constraints = [
            models.UniqueConstraint(
                fields=["yarn_name", "yarn_type", "yarn_count", "production_type"],
                name="unique_yarn_stock_pool",
            )
        ]
        indexes = [
            models.Index(
                fields=["yarn_name", "yarn_type", "yarn_count", "production_type"],
                name="idx_yarn_stock_pool",
            ),
        ]

    def __str__(self):
        prod = f" ({self.production_type})" if self.production_type else ""
        return f"{self.yarn_name} {self.yarn_count} {self.yarn_type}{prod} - {self.total_weight_kg} kg"

    # ── Derived ledger summaries ───────────────────────────────────────────
    @property
    def total_received_boxes(self):
        agg = self.intakes.aggregate(models.Sum("bags"))
        return agg["bags__sum"] or 0

    @property
    def total_received_cones(self):
        agg = self.intakes.aggregate(models.Sum("total_cones"))
        return agg["total_cones__sum"] or 0

    @property
    def total_received_weight_kg(self):
        agg = self.intakes.aggregate(models.Sum("net_weight_kg"))
        return agg["net_weight_kg__sum"] or Decimal("0.000")

    @property
    def total_received_weight_lb(self):
        agg = self.intakes.aggregate(models.Sum("net_weight_lb"))
        return agg["net_weight_lb__sum"] or Decimal("0.000")

    @property
    def total_dispatched_boxes(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_bags"))
        return agg["outcome_bags__sum"] or 0

    @property
    def total_dispatched_weight_kg(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_kg"))
        return agg["outcome_weight_kg__sum"] or Decimal("0.000")

    @property
    def total_dispatched_weight_lb(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_lb"))
        return agg["outcome_weight_lb__sum"] or Decimal("0.000")

    @property
    def price_per_kg(self):
        """Weighted average rate per kilogram calculated from contributing intakes."""
        total_kg = self.total_received_weight_kg
        if total_kg and total_kg > Decimal("0"):
            total_amt = self.intakes.aggregate(models.Sum("total_rate"))["total_rate__sum"] or Decimal("0")
            return (total_amt / Decimal(str(total_kg))).quantize(Decimal("0.01"))
        return Decimal("0.00")
