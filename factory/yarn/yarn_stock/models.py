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
        price:           price per bag calculated by remaining_total_price divided by remaining_bags (Decimal)
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
        help_text="Calculated price per bag (remaining_total_price divided by remaining_bags)."
    )
    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Cumulative total price of yarn purchases from contributing intakes (cumulativeIntakePrice). Never subtracts dispatched yarn price."
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

    def calculate_price(self):
        """Calculates price per bag by dividing remaining_total_price by remaining_bags."""
        rem_bags = self.remaining_bags or self.total_boxes or 0
        rem_total = self.remaining_total_price or Decimal("0.000000")
        if rem_bags > 0 and rem_total > Decimal("0.000000"):
            self.price = (Decimal(str(rem_total)) / Decimal(str(rem_bags))).quantize(Decimal("0.000001"))
        else:
            self.price = Decimal("0.000000")
        return self.price

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

        # total_price acts as cumulativeIntakePrice (never minus dispatching yarn price)
        if self.pk and (not self.total_price or self.total_price <= Decimal("0.000000")):
            cum_price = Decimal("0.000000")
            for intake in self.intakes.all():
                cum_price += (Decimal(str(intake.net_weight_lb or 0)) * Decimal(str(intake.rate_per_lb or 0)))
            if cum_price > Decimal("0.000000"):
                self.total_price = cum_price.quantize(Decimal("0.000001"))

        # Recalculate price: remaining_total_price divided by remaining_bags
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "price" in update_fields:
            self.calculate_price()

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
    def total_dispatched_cones(self):
        outcome_cone_expr = models.ExpressionWrapper(
            models.F("outcome_bags") * models.F("outcome_cones_per_bag"),
            output_field=models.IntegerField()
        )
        agg = self.outcomes.annotate(calc_cones=outcome_cone_expr).aggregate(models.Sum("calc_cones"))
        return agg["calc_cones__sum"] or 0

    @property
    def total_dispatched_weight_kg(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_kg"))
        return agg["outcome_weight_kg__sum"] or Decimal("0.000000")

    @property
    def total_dispatched_weight_lb(self):
        agg = self.outcomes.aggregate(models.Sum("outcome_weight_lb"))
        return agg["outcome_weight_lb__sum"] or Decimal("0.000000")

    @property
    def total_returned_boxes(self):
        from factory.yarn.sizing.models import SizingOutcome
        from django.db.models import Q
        agg = SizingOutcome.objects.filter(
            Q(yarn_outcome__stock=self) | Q(yarn_outcome__items__yarn_intake__stock=self)
        ).distinct().aggregate(models.Sum("return_bags"))
        return agg["return_bags__sum"] or Decimal("0.000000")

    @property
    def total_returned_cones(self):
        from factory.yarn.sizing.models import SizingOutcome
        from django.db.models import Q
        agg = SizingOutcome.objects.filter(
            Q(yarn_outcome__stock=self) | Q(yarn_outcome__items__yarn_intake__stock=self)
        ).distinct().aggregate(models.Sum("return_cones"))
        return agg["return_cones__sum"] or Decimal("0.000000")

    @property
    def total_returned_weight_kg(self):
        total_intake_bags = self.total_received_boxes
        total_intake_kg = self.total_received_weight_kg
        total_intake_cones = self.total_received_cones
        avg_wpb = (total_intake_kg / Decimal(str(total_intake_bags))) if total_intake_bags > 0 else Decimal("0.000000")
        avg_cpb = (Decimal(str(total_intake_cones)) / Decimal(str(total_intake_bags))) if total_intake_bags > 0 else Decimal("0.000000")
        avg_wpc = (avg_wpb / avg_cpb) if avg_cpb > 0 else Decimal("0.000000")
        return ((Decimal(str(self.total_returned_boxes)) * avg_wpb) + (Decimal(str(self.total_returned_cones)) * avg_wpc)).quantize(Decimal("0.000001"))

    @property
    def total_returned_weight_lb(self):
        return (self.total_returned_weight_kg * LB_PER_KG).quantize(Decimal("0.000001"))

    @property
    def total_returned_price(self):
        agg = self.intakes.aggregate(models.Sum("return_total_rate"))
        ret_val = agg["return_total_rate__sum"]
        if ret_val is not None and ret_val > Decimal("0.000000"):
            return ret_val
        return (self.total_returned_weight_lb * self.price_per_lb).quantize(Decimal("0.000001"))

    @property
    def available_boxes(self):
        return self.remaining_bags

    @property
    def available_cones(self):
        return self.remaining_cones

    @property
    def available_weight_kg(self):
        return self.remaining_weight_kg

    @property
    def available_weight_lb(self):
        return self.remaining_weight_lb

    @property
    def price_per_kg(self):
        """Average rate per kilogram derived from rate per pound."""
        return (self.price_per_lb * LB_PER_KG).quantize(Decimal("0.000001"))

    @property
    def price_per_lb(self):
        """Average rate per pound calculated from contributing intakes (simple average of rate_per_lb)."""
        intakes_with_rate = self.intakes.filter(rate_per_lb__gt=0)
        target = intakes_with_rate if intakes_with_rate.exists() else self.intakes
        agg = target.aggregate(models.Avg("rate_per_lb"))
        avg_val = agg["rate_per_lb__avg"]
        if avg_val is not None:
            return Decimal(str(avg_val)).quantize(Decimal("0.000001"))
        return Decimal("0.000000")

    @property
    def cumulative_intake_price(self):
        """Total cumulative valuation of all intakes that ever contributed to this pool (never decreases on dispatch)."""
        if self.total_price and self.total_price > Decimal("0.000000"):
            return self.total_price
        total = Decimal("0.000000")
        for intake in self.intakes.all():
            total += (Decimal(str(intake.net_weight_lb or 0)) * Decimal(str(intake.rate_per_lb or 0)))
        return total.quantize(Decimal("0.000001"))
