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
        self._clear_aggregate_cache()
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
    # The totals below are computed with aggregate queries. Several properties
    # depend on each other (e.g. total_returned_price -> total_returned_weight_lb
    # -> total_returned_weight_kg -> total_received_* / total_returned_*), which
    # previously re-ran the same SUM() queries ~18 times per serialization.
    # They are now memoized per instance and invalidated on save()/refresh_from_db().
    _AGG_CACHE_ATTRS = ("_intake_totals_cache", "_returned_totals_cache", "_dispatched_totals_cache")

    def _clear_aggregate_cache(self):
        for attr in self._AGG_CACHE_ATTRS:
            self.__dict__.pop(attr, None)

    def refresh_from_db(self, *args, **kwargs):
        self._clear_aggregate_cache()
        return super().refresh_from_db(*args, **kwargs)

    def _intake_totals(self):
        cache = self.__dict__.get("_intake_totals_cache")
        if cache is None:
            if hasattr(self, "_prefetched_objects_cache") and "intakes" in self._prefetched_objects_cache:
                intakes_list = self._prefetched_objects_cache["intakes"]
                bags = sum((i.bags or 0 for i in intakes_list))
                cones = sum((i.total_cones or 0 for i in intakes_list))
                kg = sum((Decimal(str(i.net_weight_kg or 0)) for i in intakes_list), Decimal("0.000000"))
                lb = sum((Decimal(str(i.net_weight_lb or 0)) for i in intakes_list), Decimal("0.000000"))
                return_rate = sum((Decimal(str(i.return_total_rate or 0)) for i in intakes_list), Decimal("0.000000"))
                cache = {"bags": bags, "cones": cones, "kg": kg, "lb": lb, "return_rate": return_rate}
            else:
                cache = self.intakes.aggregate(
                    bags=models.Sum("bags"),
                    cones=models.Sum("total_cones"),
                    kg=models.Sum("net_weight_kg"),
                    lb=models.Sum("net_weight_lb"),
                    return_rate=models.Sum("return_total_rate"),
                )
            self.__dict__["_intake_totals_cache"] = cache
        return cache

    def _dispatched_totals(self):
        cache = self.__dict__.get("_dispatched_totals_cache")
        if cache is None:
            if hasattr(self, "_prefetched_objects_cache") and "outcomes" in self._prefetched_objects_cache:
                outcomes_list = self._prefetched_objects_cache["outcomes"]
                boxes = sum((o.outcome_bags or 0 for o in outcomes_list))
                cones = sum(((o.outcome_bags or 0) * (o.outcome_cones_per_bag or 0) for o in outcomes_list))
                kg = sum((Decimal(str(o.outcome_weight_kg or 0)) for o in outcomes_list), Decimal("0.000000"))
                lb = sum((Decimal(str(o.outcome_weight_lb or 0)) for o in outcomes_list), Decimal("0.000000"))
                cache = {"boxes": boxes, "cones": cones, "kg": kg, "lb": lb}
            else:
                outcome_cone_expr = models.ExpressionWrapper(
                    models.F("outcome_bags") * models.F("outcome_cones_per_bag"),
                    output_field=models.IntegerField()
                )
                agg = self.outcomes.annotate(calc_cones=outcome_cone_expr).aggregate(
                    boxes=models.Sum("outcome_bags"),
                    cones=models.Sum("calc_cones"),
                    kg=models.Sum("outcome_weight_kg"),
                    lb=models.Sum("outcome_weight_lb"),
                )
                cache = {
                    "boxes": agg["boxes"] or 0,
                    "cones": agg["cones"] or 0,
                    "kg": agg["kg"] or Decimal("0.000000"),
                    "lb": agg["lb"] or Decimal("0.000000"),
                }
            self.__dict__["_dispatched_totals_cache"] = cache
        return cache

    def _returned_totals(self):
        cache = self.__dict__.get("_returned_totals_cache")
        if cache is None:
            from factory.yarn.sizing.models import SizingOutcome
            from django.db.models import Q
            cache = SizingOutcome.objects.filter(
                Q(yarn_outcome__stock=self) | Q(yarn_outcome__items__yarn_intake__stock=self)
            ).distinct().aggregate(
                bags=models.Sum("return_bags"),
                cones=models.Sum("return_cones"),
            )
            self.__dict__["_returned_totals_cache"] = cache
        return cache

    @property
    def total_received_boxes(self):
        return self._intake_totals()["bags"] or 0

    @property
    def total_received_cones(self):
        return self._intake_totals()["cones"] or 0

    @property
    def total_received_weight_kg(self):
        return self._intake_totals()["kg"] or Decimal("0.000000")

    @property
    def total_received_weight_lb(self):
        return self._intake_totals()["lb"] or Decimal("0.000000")

    @property
    def total_dispatched_boxes(self):
        return self._dispatched_totals()["boxes"] or 0

    @property
    def total_dispatched_cones(self):
        return self._dispatched_totals()["cones"] or 0

    @property
    def total_dispatched_weight_kg(self):
        return self._dispatched_totals()["kg"] or Decimal("0.000000")

    @property
    def total_dispatched_weight_lb(self):
        return self._dispatched_totals()["lb"] or Decimal("0.000000")

    @property
    def total_returned_boxes(self):
        return self._returned_totals()["bags"] or Decimal("0.000000")

    @property
    def total_returned_cones(self):
        return self._returned_totals()["cones"] or Decimal("0.000000")

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
        ret_val = self._intake_totals()["return_rate"]
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
        """Rate per kilogram calculated by remaining_total_price divided by remaining_weight_kg."""
        rem_weight_kg = self.remaining_weight_kg or Decimal("0.000000")
        rem_total_price = self.remaining_total_price or Decimal("0.000000")
        if rem_weight_kg > Decimal("0.000000") and rem_total_price > Decimal("0.000000"):
            return (rem_total_price / rem_weight_kg).quantize(Decimal("0.000001"))
        return (self.price_per_lb * LB_PER_KG).quantize(Decimal("0.000001"))

    @property
    def price_per_lb(self):
        """Rate per pound calculated by remaining_total_price divided by remaining_weight_lb."""
        rem_weight_lb = self.remaining_weight_lb or Decimal("0.000000")
        rem_total_price = self.remaining_total_price or Decimal("0.000000")
        if rem_weight_lb > Decimal("0.000000") and rem_total_price > Decimal("0.000000"):
            return (rem_total_price / rem_weight_lb).quantize(Decimal("0.000001"))
        return Decimal("0.000000")

    @property
    def cumulative_intake_price(self):
        """Total cumulative valuation of all intakes that ever contributed to this pool (never decreases on dispatch)."""
        if self.total_price and self.total_price > Decimal("0.000000"):
            return self.total_price
        total = Decimal("0.000000")
        intakes_list = (
            self._prefetched_objects_cache["intakes"]
            if hasattr(self, "_prefetched_objects_cache") and "intakes" in self._prefetched_objects_cache
            else self.intakes.all()
        )
        for intake in intakes_list:
            total += (Decimal(str(intake.net_weight_lb or 0)) * Decimal(str(intake.rate_per_lb or 0)))
        return total.quantize(Decimal("0.000001"))
