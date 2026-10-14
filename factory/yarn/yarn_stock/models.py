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

from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount

LB_PER_KG = Decimal("2.20462262")


class YarnStockQuerySet(models.QuerySet):
    def _resolve_fk_lookups(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k in ("yarn_name", "yarn_type", "yarn_count") and isinstance(v, str):
                new_kwargs[f"{k}__name"] = v
            else:
                new_kwargs[k] = v
        return new_kwargs

    def filter(self, *args, **kwargs):
        return super().filter(*args, **self._resolve_fk_lookups(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **self._resolve_fk_lookups(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **self._resolve_fk_lookups(kwargs))

    def get_or_create(self, defaults=None, **kwargs):
        for field, model in [
            ("yarn_name", YarnName),
            ("yarn_type", YarnType),
            ("yarn_count", YarnCount),
        ]:
            if field in kwargs and isinstance(kwargs[field], str):
                kwargs[field], _ = model.objects.get_or_create(name=kwargs[field].strip())
        return super().get_or_create(defaults=defaults, **kwargs)


class YarnStock(models.Model):
    objects = YarnStockQuerySet.as_manager()
    """
    Shared yarn inventory pool.

    Stock-identifying attributes (uniqueness constraint):
        yarn_name, yarn_type, yarn_count, production_type

    Inventory fields (current available balances):
        total_boxes:     current available boxes / bags
        cones:           current available cones
        total_weight_kg: current available weight in kilograms
        total_weight_lb: current available weight in pounds
        price:           weighted average intake price per pound (Decimal)
    """

    yarn_name = models.ForeignKey(
        YarnName,
        on_delete=models.PROTECT,
        related_name="yarn_stocks",
        help_text="Yarn Name reference"
    )
    yarn_type = models.ForeignKey(
        YarnType,
        on_delete=models.PROTECT,
        related_name="yarn_stocks",
        help_text="Yarn Type reference"
    )
    yarn_count = models.ForeignKey(
        YarnCount,
        on_delete=models.PROTECT,
        related_name="yarn_stocks",
        help_text="Yarn Count reference"
    )
    production_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Production category such as Warp, Weft, etc."
    )

    # ── Current Available / Remaining Balances ─────────────────────────────
    price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weighted average purchase rate per pound from contributing intakes."
    )
    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total price of yarn of this quality from contributing intakes."
    )
    remaining_bags = models.IntegerField(
        default=0,
        help_text="Current remaining available boxes / bags in stock."
    )
    remaining_cones = models.IntegerField(
        default=0,
        help_text="Current remaining available cones in stock."
    )
    remaining_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available weight in kilograms."
    )
    remaining_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available weight in pounds."
    )
    remaining_total_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available inventory total price / valuation."
    )

    # Legacy balance field aliases (maintained for backward compatibility)
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
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current available weight in kilograms."
    )
    total_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
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

    def __init__(self, *args, **kwargs):
        from factory.yarn.yarn_name.models import YarnName
        from factory.yarn.yarn_type.models import YarnType
        from factory.yarn.yarn_count.models import YarnCount

        aliases = [
            (["yarn_name", "yarnName", "yarn_name_id", "yarnNameId"], "yarn_name", YarnName),
            (["yarn_type", "yarnType", "yarn_type_id", "yarnTypeId"], "yarn_type", YarnType),
            (["yarn_count", "yarnCount", "yarn_count_id", "yarnCountId"], "yarn_count", YarnCount),
        ]
        for keys, target, model in aliases:
            val = None
            for k in keys:
                if k in kwargs and kwargs[k] not in (None, ""):
                    val = kwargs.pop(k)
                    break
            if val is not None:
                if isinstance(val, model):
                    kwargs[target] = val
                elif isinstance(val, int) or (isinstance(val, str) and val.strip().isdigit()):
                    kwargs[target] = model.objects.get(pk=int(val))
                elif isinstance(val, str) and val.strip():
                    kwargs[target], _ = model.objects.get_or_create(name=val.strip())
            for k in keys:
                if k != target:
                    kwargs.pop(k, None)
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Keep remaining fields and legacy balance aliases synchronized
        if self.remaining_bags and not self.total_boxes:
            self.total_boxes = self.remaining_bags
        elif self.total_boxes and not self.remaining_bags:
            self.remaining_bags = self.total_boxes

        if self.remaining_cones and not self.cones:
            self.cones = self.remaining_cones
        elif self.cones and not self.remaining_cones:
            self.remaining_cones = self.cones

        if self.remaining_weight_kg and not self.total_weight_kg:
            self.total_weight_kg = self.remaining_weight_kg
        elif self.total_weight_kg and not self.remaining_weight_kg:
            self.remaining_weight_kg = self.total_weight_kg

        if self.remaining_weight_lb and not self.total_weight_lb:
            self.total_weight_lb = self.remaining_weight_lb
        elif self.total_weight_lb and not self.remaining_weight_lb:
            self.remaining_weight_lb = self.total_weight_lb

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["yarn_name__name", "yarn_count__name", "production_type", "-id"]
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
        yname = self.yarn_name.name if self.yarn_name else ""
        ycount = self.yarn_count.name if self.yarn_count else ""
        ytype = self.yarn_type.name if self.yarn_type else ""
        return f"{yname} {ycount} {ytype}{prod} - {self.total_weight_kg} kg"

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
        return agg["net_weight_kg__sum"] or Decimal("0.000000")

    @property
    def total_received_weight_lb(self):
        agg = self.intakes.aggregate(models.Sum("net_weight_lb"))
        return agg["net_weight_lb__sum"] or Decimal("0.000000")

    @property
    def total_dispatched_boxes(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_bags"))
        return agg["outcome_bags__sum"] or 0

    @property
    def total_dispatched_weight_kg(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_kg"))
        return agg["outcome_weight_kg__sum"] or Decimal("0.000000")

    @property
    def total_dispatched_weight_lb(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_lb"))
        return agg["outcome_weight_lb__sum"] or Decimal("0.000000")

    @property
    def price_per_kg(self):
        """Weighted average rate per kilogram calculated from contributing intakes."""
        total_kg = self.total_received_weight_kg
        if total_kg and total_kg > Decimal("0"):
            total_amt = self.intakes.aggregate(models.Sum("total_rate"))["total_rate__sum"] or Decimal("0")
            return (total_amt / Decimal(str(total_kg))).quantize(Decimal("0.000001"))
        return Decimal("0.000000")

    @property
    def price_per_lb(self):
        """Weighted average rate per pound calculated from contributing intakes."""
        total_lb = self.total_received_weight_lb
        if total_lb and total_lb > Decimal("0"):
            total_amt = self.intakes.aggregate(models.Sum("total_rate"))["total_rate__sum"] or Decimal("0")
            return (total_amt / Decimal(str(total_lb))).quantize(Decimal("0.000001"))
        return Decimal("0.000000")
