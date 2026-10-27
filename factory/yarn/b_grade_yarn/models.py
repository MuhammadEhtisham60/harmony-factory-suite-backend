"""
B-Grade Yarn model.

Represents B-grade / secondary yarn inventory.
Boxes and price are explicitly excluded from this model, tracking
quantities strictly by cones and weight (kg & lb).
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount

LB_PER_KG = Decimal("2.20462262")


class BGradeYarnQuerySet(models.QuerySet):
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


class BGradeYarn(models.Model):
    """
    B-Grade Yarn model without boxes or price.

    Quality specification:
        yarn_name: Yarn name FK
        yarn_type: Yarn type FK
        yarn_count: Yarn count FK
        production_type: Production category (e.g. Self, Conversion)

    Physical measurements:
        cones: total available / recorded cones
        weight_kg: weight in kilograms
        weight_lb: weight in pounds (calculated via LB_PER_KG)
    """
    objects = BGradeYarnQuerySet.as_manager()

    yarn_name = models.ForeignKey(
        YarnName,
        on_delete=models.PROTECT,
        related_name="b_grade_yarns",
        help_text="Yarn Name reference"
    )
    yarn_type = models.ForeignKey(
        YarnType,
        on_delete=models.PROTECT,
        related_name="b_grade_yarns",
        help_text="Yarn Type reference"
    )
    yarn_count = models.ForeignKey(
        YarnCount,
        on_delete=models.PROTECT,
        related_name="b_grade_yarns",
        help_text="Yarn Count reference"
    )
    production_type = models.CharField(
        max_length=100,
        blank=True,
        default="Self",
        help_text="Production category such as Self or Conversion"
    )

    # ── Physical quantities (No boxes/bags, No prices) ──────────────────────
    cones = models.PositiveIntegerField(
        default=0,
        help_text="Number of cones in this B-grade batch"
    )
    weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight in kilograms"
    )
    weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight in pounds"
    )

    lot_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Lot / Batch number identifier"
    )
    entry_date = models.DateField(
        default=timezone.localdate,
        help_text="Date when B-grade yarn was received / recorded"
    )
    remarks = models.TextField(
        blank=True,
        default="",
        help_text="Remarks, defects, or inspection notes"
    )

    # ── Audit fields ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_b_grade_yarns"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_b_grade_yarns"
    )

    def __init__(self, *args, **kwargs):
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

        if "weightKg" in kwargs and "weight_kg" not in kwargs:
            kwargs["weight_kg"] = kwargs.pop("weightKg")
        if "weightLb" in kwargs and "weight_lb" not in kwargs:
            kwargs["weight_lb"] = kwargs.pop("weightLb")
        if "lotNumber" in kwargs and "lot_number" not in kwargs:
            kwargs["lot_number"] = kwargs.pop("lotNumber")
        if "productionType" in kwargs and "production_type" not in kwargs:
            kwargs["production_type"] = kwargs.pop("productionType")
        if "entryDate" in kwargs and "entry_date" not in kwargs:
            kwargs["entry_date"] = kwargs.pop("entryDate")

        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Auto-compute lb from kg or kg from lb if one is given
        if self.weight_kg and (not self.weight_lb or self.weight_lb <= Decimal("0.000000")):
            self.weight_lb = (Decimal(str(self.weight_kg)) * LB_PER_KG).quantize(Decimal("0.000001"))
        elif self.weight_lb and (not self.weight_kg or self.weight_kg <= Decimal("0.000000")):
            self.weight_kg = (Decimal(str(self.weight_lb)) / LB_PER_KG).quantize(Decimal("0.000001"))

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-entry_date", "-id"]
        verbose_name = "B-Grade Yarn"
        verbose_name_plural = "B-Grade Yarns"
        indexes = [
            models.Index(
                fields=["yarn_name", "yarn_type", "yarn_count", "production_type"],
                name="idx_b_grade_yarn_quality",
            ),
            models.Index(fields=["entry_date"], name="idx_b_grade_yarn_date"),
        ]

    def __str__(self):
        prod = f" ({self.production_type})" if self.production_type else ""
        yname = self.yarn_name.name if self.yarn_name else ""
        ycount = self.yarn_count.name if self.yarn_count else ""
        ytype = self.yarn_type.name if self.yarn_type else ""
        return f"B-Grade: {yname} {ycount} {ytype}{prod} - {self.cones} cones ({self.weight_kg} kg)"
