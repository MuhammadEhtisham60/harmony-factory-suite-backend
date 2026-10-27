"""
YarnIntake and YarnOutcome models for the Yarn module.

Calculation rules (all Decimal, never float):
  LB_PER_KG = Decimal("2.20462262")

  YarnIntake:
    total_cones       = bags * cones_per_bag
    total_rate        = net_weight_lb * rate_per_lb
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

from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.purchase.supplier.models import Supplier
from factory.yarn.processing import profile_for
from factory.yarn.sizing.models import Sizing
from factory.yarn.warping.models import Warping
from factory.yarn.yarn_stock.models import YarnStock, LB_PER_KG


class YarnIntakeQuerySet(models.QuerySet):
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


class YarnIntake(models.Model):
    objects = YarnIntakeQuerySet.as_manager()
    """
    Records a batch of yarn received from a supplier.

    Source-input fields (frontend-provided):
        bags, cones_per_bag, rate_per_lb, weight_per_bag_kg

    Backend-calculated (read-only from API perspective):
        total_cones, total_rate, net_weight_kg, net_weight_lb

    Denormalized summary (recalculated from YarnOutcome records after every mutation):
        outcome_bags, outcome_weight_kg, outcome_weight_lb
        remaining_bags, remaining_weight_kg, remaining_weight_lb
    """

    yarn_name = models.ForeignKey(
        YarnName,
        on_delete=models.PROTECT,
        related_name="yarn_intakes",
        help_text="Yarn Name reference"
    )
    yarn_type = models.ForeignKey(
        YarnType,
        on_delete=models.PROTECT,
        related_name="yarn_intakes",
        help_text="Yarn Type reference"
    )
    yarn_count = models.ForeignKey(
        YarnCount,
        on_delete=models.PROTECT,
        related_name="yarn_intakes",
        help_text="Yarn Count reference"
    )

    set_no = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Batch / Set number. Auto-generated like BATCH-01 if left blank."
    )

    intake_date = models.DateField()

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="yarn_intakes"
    )

    stock = models.ForeignKey(
        YarnStock,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="intakes",
        help_text="Shared inventory pool this intake contributes to."
    )

    production_type = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    # ── Source inputs ──────────────────────────────────────────────────────
    bags = models.PositiveIntegerField(default=0)
    cones_per_bag = models.PositiveIntegerField(default=0)
    rate_per_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Price / Rate per pound (LB) of yarn."
    )
    weight_per_bag_kg = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    # ── Backend-calculated intake totals ───────────────────────────────────
    total_cones = models.PositiveIntegerField(default=0)
    total_rate = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    net_weight_kg = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    net_weight_lb = models.DecimalField(max_digits=15, decimal_places=6, default=0)

    # ── Denormalized outcome summary (recalculated from YarnOutcome) ───────
    outcome_bags = models.PositiveIntegerField(default=0)
    outcome_weight_kg = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    outcome_weight_lb = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    outcome_total_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total monetary value of outcomes dispatched from this intake."
    )

    # ── Returned from sizing summary (recalculated from SizingOutcome) ────
    return_bags = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total bags returned from sizing"
    )
    return_cones = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total cones returned from sizing"
    )
    return_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total weight in kg returned from sizing"
    )
    return_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total weight in lb returned from sizing"
    )
    return_total_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total monetary price / value of yarn returned from sizing to this intake batch."
    )

    # ── Remaining stock (recalculated from YarnOutcome & SizingOutcome) ───
    remaining_bags = models.PositiveIntegerField(default=0)
    remaining_cones = models.PositiveIntegerField(
        default=0,
        help_text="Current remaining available cones in this intake batch."
    )
    remaining_weight_kg = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    remaining_weight_lb = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    remaining_total_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available inventory total price / valuation in this intake batch."
    )

    class PaymentStatusChoices(models.TextChoices):
        UNPAID = "Unpaid", "Unpaid"
        PARTIALLY_PAID = "Partially Paid", "Partially Paid"
        PAID = "Paid", "Paid"

    # ── Payment & Payables tracking ───────────────────────────────────────
    amount_paid = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total amount paid to supplier for this intake batch"
    )
    amount_due = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Remaining payable amount due to supplier for this intake batch"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID,
        help_text="Payment status: Unpaid, Partially Paid, Paid"
    )

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

    class Meta:
        ordering = ["-intake_date", "-id"]
        verbose_name = "Yarn Intake"
        verbose_name_plural = "Yarn Intakes"

    def __str__(self):
        name = self.yarn_name.name if self.yarn_name else ""
        return f"{name} - {self.set_no}"

    def calculate_intake_fields(self):
        """
        Recalculate all derived intake fields from source inputs.
        Call before saving a new or updated YarnIntake.
        Preserves full decimal precision without rounding intermediate values.
        """
        bags = Decimal(str(self.bags))
        cones_per_bag = Decimal(str(self.cones_per_bag))
        rate_per_lb = Decimal(str(self.rate_per_lb))
        weight_per_bag_kg = Decimal(str(self.weight_per_bag_kg))

        self.total_cones = int(bags * cones_per_bag)
        self.net_weight_kg = bags * weight_per_bag_kg
        self.net_weight_lb = self.net_weight_kg * LB_PER_KG
        if not self.outcome_bags and not self.return_bags:
            self.total_rate = (self.net_weight_lb * rate_per_lb).quantize(Decimal("0.000001"))
        elif self.remaining_total_rate is not None:
            self.total_rate = self.remaining_total_rate

    @property
    def initial_total_rate(self):
        """Initial invoice total price when this batch was received."""
        return (Decimal(str(self.net_weight_lb or 0)) * Decimal(str(self.rate_per_lb or 0))).quantize(Decimal("0.000001"))

    def init_remaining_stock(self):
        """
        Initialise remaining stock on first creation (no outcomes yet).
        """
        self.remaining_bags = self.bags
        self.remaining_cones = self.total_cones
        self.remaining_weight_kg = self.net_weight_kg
        self.remaining_weight_lb = self.net_weight_lb
        self.remaining_total_rate = self.total_rate
        self.outcome_bags = 0
        self.outcome_weight_kg = Decimal("0")
        self.outcome_weight_lb = Decimal("0")
        self.outcome_total_rate = Decimal("0.000000")
        self.return_bags = Decimal("0.000000")
        self.return_cones = Decimal("0.000000")
        self.return_weight_kg = Decimal("0.000000")
        self.return_weight_lb = Decimal("0.000000")
        self.return_total_rate = Decimal("0.000000")

    @classmethod
    def generate_next_batch_no(cls):
        """
        Auto-generates sequential batch identifiers like BATCH-01, BATCH-02, ...
        Finds the highest existing numeric suffix matching BATCH-<number>
        and returns the next formatted number (with at least 2 digits).
        """
        import re
        batch_intakes = cls.objects.filter(set_no__istartswith="BATCH-").values_list("set_no", flat=True)
        max_num = 0
        for val in batch_intakes:
            match = re.match(r"^BATCH-(\d+)$", val, re.IGNORECASE)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        next_num = max_num + 1
        candidate = f"BATCH-{next_num:02d}"
        while cls.objects.filter(set_no__iexact=candidate).exists():
            next_num += 1
            candidate = f"BATCH-{next_num:02d}"
        return candidate

    def save(self, *args, **kwargs):
        if not self.set_no or not str(self.set_no).strip():
            self.set_no = self.generate_next_batch_no()
        self.calculate_intake_fields()
        if not self.pk and not self.remaining_bags and self.bags and not self.outcome_bags:
            self.init_remaining_stock()
        prod_type = (self.production_type or "").strip()
        if not prod_type:
            prod_type = "Conversion" if (self.rate_per_lb or Decimal("0")) == Decimal("0") else "Self"
        elif prod_type.lower() == "conversion":
            prod_type = "Conversion"
        elif prod_type.lower() == "self":
            prod_type = "Self"
        self.production_type = prod_type

        from factory.yarn.yarn_stock.services import get_or_create_yarn_stock, recalculate_yarn_stock
        old_stock = self.stock
        need_new_stock = (
            not self.stock_id
            or (self.stock and (self.stock.production_type or "").strip() != prod_type)
        )
        if need_new_stock:
            self.stock = get_or_create_yarn_stock(
                yarn_name=self.yarn_name,
                yarn_type=self.yarn_type,
                yarn_count=self.yarn_count,
                production_type=prod_type,
                user=self.created_by,
            )
        # Calculate amount_due and payment_status
        tot = self.initial_total_rate or self.total_rate or Decimal("0.000000")
        paid = self.amount_paid if self.amount_paid is not None else Decimal("0.000000")
        if tot > Decimal("0.000000"):
            if paid >= tot:
                self.amount_due = Decimal("0.000000")
                self.payment_status = self.PaymentStatusChoices.PAID
            elif paid > Decimal("0.000000"):
                self.amount_due = tot - paid
                self.payment_status = self.PaymentStatusChoices.PARTIALLY_PAID
            else:
                self.amount_due = tot
                self.payment_status = self.PaymentStatusChoices.UNPAID
        else:
            self.amount_due = Decimal("0.000000")
            self.payment_status = self.PaymentStatusChoices.PAID

        super().save(*args, **kwargs)
        if self.stock_id and not kwargs.get("update_fields"):
            recalculate_yarn_stock(self.stock)
            if old_stock and old_stock.id != self.stock_id:
                recalculate_yarn_stock(old_stock)

    def delete(self, *args, **kwargs):
        stock = self.stock
        super().delete(*args, **kwargs)
        if stock:
            from factory.yarn.yarn_stock.services import recalculate_yarn_stock
            recalculate_yarn_stock(stock)


class YarnOutcome(models.Model):
    """
    Records yarn dispatched from a YarnIntake batch.

    Rules:
      Sizing:
        yarn_buyer  must be None
        total_price saves valuation of dispatched yarn (Rs)
        sizing       required (FK to Sizing)
        warping      must be None

      Warping:
        yarn_buyer  must be None
        total_price saves valuation of dispatched yarn (Rs)
        warping      required (FK to Warping)
        sizing       must be None

      Weft:
        yarn_buyer  must be None
        total_price saves valuation of dispatched yarn (Rs)
        sizing / warping  must be None

      Sold:
        yarn_buyer  required
        total_price saves agreed sale price or valuation of dispatched yarn
        sizing / warping  must be None

    Sizing and Warping are *processing* dispatches: they share the same set
    return, beam and ledger workflow (see `factory.yarn.processing`).

    outcome_weight_kg = outcome_bags * outcome_weight_per_bag_kg
    outcome_weight_lb = outcome_weight_kg * LB_PER_KG

    After every CREATE / UPDATE / DELETE the parent YarnIntake summary
    is recalculated from the actual YarnOutcome rows.
    """

    class OutcomeTypeChoices(models.TextChoices):
        SIZING = "Sizing", "Sizing"
        WARPING = "Warping", "Warping"
        WEFT = "Weft", "Weft"
        SOLD = "Sold", "Sold"

    stock = models.ForeignKey(
        YarnStock,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="outcomes",
        help_text="Shared stock pool this outcome is dispatched from."
    )

    yarn_intakes = models.ManyToManyField(
        YarnIntake,
        through="YarnOutcomeItem",
        related_name="outcomes",
        blank=True,
        help_text="Contributing yarn intake batches."
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
        decimal_places=6,
        default=0
    )

    # Backend-calculated
    outcome_weight_kg = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    outcome_weight_lb = models.DecimalField(max_digits=15, decimal_places=6, default=0)

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

    warping = models.ForeignKey(
        Warping,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yarn_outcomes"
    )

    class StatusChoices(models.TextChoices):
        IN_SIZING = "In Sizing", "In Sizing"
        IN_WARPING = "In Warping", "In Warping"
        PARTIALLY_RECEIVED = "Partially Received", "Partially Received"
        RECEIVED = "Received", "Received"
        DISPATCHED = "Dispatched", "Dispatched"
        COMPLETED = "Completed", "Completed"

    total_price = models.DecimalField(max_digits=15, decimal_places=6, default=0)

    status = models.CharField(
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.IN_SIZING
    )

    outcome_date = models.DateField()

    notes = models.TextField(blank=True, default="")

    # ── Merged Sizing Mill Stock ──────────────────────────────────────────
    merged_sizing_bags = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="Bags merged from existing sizing stock of the same quality at the sizing mill."
    )
    merged_sizing_cones = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="Cones merged from existing sizing stock of the same quality at the sizing mill."
    )
    merged_b_grade_cones = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="B-grade cones merged from existing warping/sizing stock at the unit."
    )
    merged_from_sizing_outcomes = models.ManyToManyField(
        "factory.SizingOutcome",
        blank=True,
        related_name="merged_into_yarn_outcomes",
        help_text="Previous sizing outcome sets whose remaining balance was merged into this dispatch/set."
    )

    # ── Dispatched B-Grade Cones ──────────────────────────────────────────
    b_grade_cones = models.PositiveIntegerField(
        default=0,
        help_text="Total B-grade cones dispatched in this outcome"
    )
    b_grade_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total weight of dispatched B-grade cones in KG"
    )
    b_grade_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total weight of dispatched B-grade cones in LB"
    )

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

    def __init__(self, *args, **kwargs):
        intake = kwargs.pop("yarn_intake", None) or kwargs.pop("yarnIntake", None)
        intake_id = kwargs.pop("yarn_intake_id", None) or kwargs.pop("yarnIntakeId", None)
        super().__init__(*args, **kwargs)
        if intake is not None:
            self._initial_yarn_intake = intake
        elif intake_id is not None:
            self._initial_yarn_intake = intake_id

    def __str__(self):
        name = ""
        if self.stock and self.stock.yarn_name:
            name = self.stock.yarn_name.name
        elif self.pk and hasattr(self, "items") and self.items.exists():
            first_item = self.items.select_related("yarn_intake__yarn_name").first()
            if first_item and first_item.yarn_intake and first_item.yarn_intake.yarn_name:
                name = first_item.yarn_intake.yarn_name.name
        return (
            f"{name or 'Yarn'} - "
            f"{self.outcome_type} - "
            f"{self.outcome_bags} bags"
        )

    @property
    def processing_profile(self):
        """ProcessingProfile for Sizing / Warping dispatches, None for Weft / Sold."""
        return profile_for(self)

    @property
    def processing_unit(self):
        """The mill master record (Sizing or Warping) this dispatch was sent to."""
        profile = self.processing_profile
        return profile.unit_of(self) if profile else None

    @property
    def processing_unit_name(self):
        profile = self.processing_profile
        return profile.unit_name_of(self) if profile else ""

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        profile = self.processing_profile
        if profile:
            if not getattr(self, profile.unit_id_field):
                raise ValidationError({
                    profile.unit_field: f"{profile.label} reference is required for {profile.label} outcome type."
                })
            if self.yarn_buyer_id:
                self.yarn_buyer = None
                self.yarn_buyer_id = None
        for other in ("sizing", "warping"):
            if (not profile or other != profile.unit_field) and getattr(self, f"{other}_id"):
                setattr(self, other, None)
                setattr(self, f"{other}_id", None)

    def calculate_outcome_fields(self):
        """
        Recalculate backend-derived outcome weight fields and total_price of dispatched yarn.
        If items exist, aggregates bags and weights from items and computes total dispatched yarn price.
        Incorporates any dispatched B-grade yarn cones and their weights.
        """
        standard_kg = Decimal("0.000000")
        standard_lb = Decimal("0.000000")
        if self.pk and hasattr(self, "items") and self.items.exists():
            item_agg = self.items.aggregate(
                total_bags=models.Sum("bags"),
                total_kg=models.Sum("weight_kg"),
                total_lb=models.Sum("weight_lb"),
            )
            self.outcome_bags = item_agg["total_bags"] or 0
            standard_kg = item_agg["total_kg"] or Decimal("0.000000")
            standard_lb = item_agg["total_lb"] or Decimal("0.000000")
            if self.outcome_bags > 0:
                self.outcome_weight_per_bag_kg = (standard_kg / Decimal(str(self.outcome_bags))).quantize(Decimal("0.000001"))
        else:
            outcome_bags = Decimal(str(self.outcome_bags or 0))
            weight_per_bag = Decimal(str(self.outcome_weight_per_bag_kg or 0))
            standard_kg = outcome_bags * weight_per_bag
            standard_lb = standard_kg * LB_PER_KG

        # Aggregate B-grade items if present
        if self.pk and hasattr(self, "b_grade_items") and self.b_grade_items.exists():
            bg_agg = self.b_grade_items.aggregate(
                total_cones=models.Sum("cones"),
                total_kg=models.Sum("weight_kg"),
                total_lb=models.Sum("weight_lb"),
            )
            self.b_grade_cones = (bg_agg["total_cones"] or 0) + (self.merged_b_grade_cones or 0)
            self.b_grade_weight_kg = bg_agg["total_kg"] or Decimal("0.000000")
            self.b_grade_weight_lb = bg_agg["total_lb"] or Decimal("0.000000")
        else:
            self.b_grade_cones = (getattr(self, "b_grade_cones", 0) or 0) or (self.merged_b_grade_cones or 0)
            self.b_grade_weight_kg = getattr(self, "b_grade_weight_kg", Decimal("0.000000")) or Decimal("0.000000")
            self.b_grade_weight_lb = getattr(self, "b_grade_weight_lb", Decimal("0.000000")) or Decimal("0.000000")

        self.outcome_weight_kg = standard_kg + self.b_grade_weight_kg
        self.outcome_weight_lb = standard_lb + self.b_grade_weight_lb

        # Resolve stock if not set yet
        stock = self.stock
        if not stock:
            if self.pk and hasattr(self, "items") and self.items.exists():
                first_item = self.items.select_related("yarn_intake__stock").first()
                if first_item and first_item.yarn_intake and first_item.yarn_intake.stock:
                    stock = first_item.yarn_intake.stock
                    self.stock = stock
            elif hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake:
                intake = self._initial_yarn_intake
                if isinstance(intake, int):
                    intake = YarnIntake.objects.filter(pk=intake).first()
                if intake and getattr(intake, "stock", None):
                    stock = intake.stock
                    self.stock = stock

        # Calculate total_price: dispatched yarn price = Weight in lb * (remaining_total_price / remaining_weight_lb)
        if not self.total_price or self.total_price <= Decimal("0"):
            pool_rate = Decimal("0.000000")
            if stock:
                rem_w_lb = Decimal(str(stock.remaining_weight_lb or 0))
                rem_tp = Decimal(str(stock.remaining_total_price or 0))
                if rem_w_lb > Decimal("0.000000") and rem_tp > Decimal("0.000000"):
                    pool_rate = (rem_tp / rem_w_lb).quantize(Decimal("0.000001"))
                elif stock.price_per_lb and stock.price_per_lb > Decimal("0.000000"):
                    pool_rate = stock.price_per_lb

            if pool_rate > Decimal("0.000000"):
                self.total_price = (self.outcome_weight_lb * pool_rate).quantize(Decimal("0.000001"))
            else:
                items_val = Decimal("0.000000")
                if self.pk and hasattr(self, "items") and self.items.exists():
                    for item in self.items.select_related("yarn_intake").all():
                        if item.yarn_intake and item.yarn_intake.rate_per_lb:
                            items_val += (item.weight_lb or Decimal("0")) * item.yarn_intake.rate_per_lb
                if items_val > Decimal("0"):
                    self.total_price = items_val.quantize(Decimal("0.000001"))
                elif hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake:
                    itk = self._initial_yarn_intake
                    if isinstance(itk, int):
                        itk = YarnIntake.objects.filter(pk=itk).first()
                    if itk and itk.rate_per_lb:
                        self.total_price = (self.outcome_weight_lb * itk.rate_per_lb).quantize(Decimal("0.000001"))

    def save(self, *args, **kwargs):
        if self.merged_sizing_bags is None:
            self.merged_sizing_bags = 0
        if self.merged_sizing_cones is None:
            self.merged_sizing_cones = 0
        if not self.pk:
            profile = self.processing_profile
            if profile and self.status == self.StatusChoices.IN_SIZING:
                self.status = profile.in_progress_status
            elif self.outcome_type in (self.OutcomeTypeChoices.WEFT, self.OutcomeTypeChoices.SOLD) and self.status == self.StatusChoices.IN_SIZING:
                self.status = self.StatusChoices.DISPATCHED
        self.calculate_outcome_fields()
        if not self.stock_id:
            if self.pk and hasattr(self, "items") and self.items.exists():
                first_item = self.items.select_related("yarn_intake__stock").first()
                if first_item and first_item.yarn_intake and first_item.yarn_intake.stock:
                    self.stock = first_item.yarn_intake.stock
            elif hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake:
                intake = self._initial_yarn_intake
                if isinstance(intake, int):
                    intake = YarnIntake.objects.filter(pk=intake).first()
                if intake and getattr(intake, "stock", None):
                    self.stock = intake.stock
        super().save(*args, **kwargs)
        if hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake and not self.items.exists():
            intake = self._initial_yarn_intake
            if isinstance(intake, int):
                intake = YarnIntake.objects.filter(pk=intake).first()
            if intake:
                YarnOutcomeItem.objects.create(
                    yarn_outcome=self,
                    yarn_intake=intake,
                    bags=self.outcome_bags,
                    cones_per_bag=self.outcome_cones_per_bag or intake.cones_per_bag,
                    weight_per_bag_kg=self.outcome_weight_per_bag_kg or intake.weight_per_bag_kg,
                )
                self.calculate_outcome_fields()
                super().save(update_fields=[
                    "outcome_bags",
                    "outcome_weight_kg",
                    "outcome_weight_lb",
                    "outcome_weight_per_bag_kg",
                    "total_price",
                ])

    def delete(self, *args, **kwargs):
        # Restore merged sizing balance if this outcome was deleted before completion
        merged_sos = list(self.merged_from_sizing_outcomes.all()) if self.pk else []
        merged_bags = self.merged_sizing_bags or 0
        merged_cones = self.merged_sizing_cones or 0
        merged_bg_cones = self.merged_b_grade_cones or 0

        stock = self.stock
        intake_ids = list(self.items.values_list("yarn_intake_id", flat=True)) if self.pk else []
        bg_items_to_restore = list(self.b_grade_items.all()) if self.pk else []
        super().delete(*args, **kwargs)

        if bg_items_to_restore:
            from factory.yarn.b_grade_yarn.models import BGradeYarn
            for item in bg_items_to_restore:
                unreturned_cones = max(0, item.cones - (item.returned_cones or 0))
                unreturned_kg = max(Decimal("0.000000"), item.weight_kg - (item.returned_weight_kg or Decimal("0.000000")))
                unreturned_lb = max(Decimal("0.000000"), item.weight_lb - (item.returned_weight_lb or Decimal("0.000000")))
                if unreturned_cones > 0 or unreturned_kg > Decimal("0.000000"):
                    try:
                        bg_obj = BGradeYarn.objects.select_for_update().get(pk=item.b_grade_yarn_id)
                        bg_obj.cones += unreturned_cones
                        bg_obj.weight_kg += unreturned_kg
                        bg_obj.weight_lb += unreturned_lb
                        bg_obj.save(update_fields=["cones", "weight_kg", "weight_lb", "updated_at"])
                    except BGradeYarn.DoesNotExist:
                        pass

        if merged_sos:
            from factory.yarn.sizing.services import sync_yarn_outcome_status
            for source_so in merged_sos:
                source_so.remaining_bags_on_sizing_stock += merged_bags
                source_so.remaining_cones_on_sizing_stock += merged_cones
                source_so.remaining_b_grade_cones = (source_so.remaining_b_grade_cones or 0) + merged_bg_cones
                source_so.save(update_fields=["remaining_bags_on_sizing_stock", "remaining_cones_on_sizing_stock", "remaining_b_grade_cones", "updated_at"])
                sync_yarn_outcome_status(source_so.yarn_outcome)

        if stock:
            from factory.yarn.yarn_stock.services import recalculate_yarn_stock
            recalculate_yarn_stock(stock)
        if intake_ids:
            from factory.yarn.yarn_intake.services import recalculate_yarn_intake_stock
            for intake in YarnIntake.objects.filter(id__in=intake_ids):
                recalculate_yarn_intake_stock(intake)

    @property
    def total_set_bags(self):
        """Total bags available for the sizing set (dispatched from warehouse + merged from sizing mill)."""
        return (self.outcome_bags or 0) + (self.merged_sizing_bags or 0)

    @property
    def total_set_cones(self):
        """Total cones available for the sizing set."""
        cpb = self.outcome_cones_per_bag or 24
        dispatched_cones = (self.outcome_bags or 0) * cpb
        merged_cones = (self.merged_sizing_bags or 0) * cpb + (self.merged_sizing_cones or 0)
        return dispatched_cones + merged_cones

    @property
    def primary_intake(self):
        if self.pk and hasattr(self, "items"):
            first_item = self.items.select_related("yarn_intake").first()
            if first_item:
                return first_item.yarn_intake
        if hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake:
            if isinstance(self._initial_yarn_intake, int):
                return YarnIntake.objects.filter(pk=self._initial_yarn_intake).first()
            return self._initial_yarn_intake
        return None

    @property
    def yarn_intake(self):
        """Backward-compatible property returning primary intake."""
        return self.primary_intake

    @yarn_intake.setter
    def yarn_intake(self, value):
        self._initial_yarn_intake = value

    @property
    def yarn_intake_id(self):
        if hasattr(self, "_initial_yarn_intake") and self._initial_yarn_intake:
            if isinstance(self._initial_yarn_intake, int):
                return self._initial_yarn_intake
            return getattr(self._initial_yarn_intake, "id", None)
        intake = self.primary_intake
        return intake.id if intake else None

    @yarn_intake_id.setter
    def yarn_intake_id(self, value):
        self._initial_yarn_intake = value

    @property
    def total_beams(self):
        if self.pk and hasattr(self, "beam_assignments"):
            from factory.beam.models import Beam
            from factory.yarn.sizing.models import SizingBeamAssignment
            return Beam.objects.filter(
                sizing_assignments__yarn_outcome=self
            ).exclude(
                sizing_assignments__status=SizingBeamAssignment.StatusChoices.RELEASED
            ).distinct().count()
        return 0


class YarnOutcomeItem(models.Model):
    """
    Records yarn dispatched from a specific YarnIntake batch as part of a YarnOutcome.
    Enables dispatching yarn from multiple intakes within a single outcome dispatch.
    """
    yarn_outcome = models.ForeignKey(
        YarnOutcome,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Parent yarn outcome dispatch"
    )
    yarn_intake = models.ForeignKey(
        YarnIntake,
        on_delete=models.PROTECT,
        related_name="outcome_items",
        help_text="Specific yarn intake batch dispatched"
    )
    bags = models.PositiveIntegerField(
        default=0,
        help_text="Number of bags dispatched from this intake"
    )
    cones_per_bag = models.PositiveIntegerField(
        default=0,
        help_text="Cones per bag for this intake at dispatch time"
    )
    weight_per_bag_kg = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
        help_text="Weight per bag in KG from this intake"
    )
    weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=0,
        help_text="Calculated weight in KG (bags * weight_per_bag_kg)"
    )
    weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=0,
        help_text="Calculated weight in LB (weight_kg * LB_PER_KG)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Yarn Outcome Item"
        verbose_name_plural = "Yarn Outcome Items"

    def calculate_weights(self):
        bags_dec = Decimal(str(self.bags or 0))
        wpb_dec = Decimal(str(self.weight_per_bag_kg or 0))
        self.weight_kg = (bags_dec * wpb_dec).quantize(Decimal("0.000001"))
        self.weight_lb = (self.weight_kg * LB_PER_KG).quantize(Decimal("0.000001"))

    def save(self, *args, **kwargs):
        if not self.weight_per_bag_kg and self.yarn_intake_id:
            self.weight_per_bag_kg = self.yarn_intake.weight_per_bag_kg
        if not self.cones_per_bag and self.yarn_intake_id:
            self.cones_per_bag = self.yarn_intake.cones_per_bag
        self.calculate_weights()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        intake = self.yarn_intake
        super().delete(*args, **kwargs)
        if intake:
            from factory.yarn.yarn_intake.services import recalculate_yarn_intake_stock
            recalculate_yarn_intake_stock(intake)

    def __str__(self):
        intake_str = self.yarn_intake.set_no if self.yarn_intake else f"Intake #{self.yarn_intake_id}"
        return f"Outcome #{self.yarn_outcome_id} -> {intake_str} ({self.bags} bags)"


class YarnOutcomeBGradeItem(models.Model):
    """
    Records B-grade yarn cones dispatched as part of a YarnOutcome dispatch.
    Tracks cones and weight deducted from a specific BGradeYarn batch.
    """
    yarn_outcome = models.ForeignKey(
        YarnOutcome,
        on_delete=models.CASCADE,
        related_name="b_grade_items",
        help_text="Parent yarn outcome dispatch"
    )
    b_grade_yarn = models.ForeignKey(
        "factory.BGradeYarn",
        on_delete=models.PROTECT,
        related_name="outcome_items",
        help_text="Specific B-grade yarn batch dispatched"
    )
    cones = models.PositiveIntegerField(
        default=0,
        help_text="Number of B-grade cones dispatched from this batch"
    )
    weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight of dispatched cones in KG"
    )
    weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight of dispatched cones in LB"
    )
    returned_cones = models.PositiveIntegerField(
        default=0,
        help_text="Number of B-grade cones returned to stock from warping/sizing"
    )
    returned_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight of returned cones in KG"
    )
    returned_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weight of returned cones in LB"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Yarn Outcome B-Grade Item"
        verbose_name_plural = "Yarn Outcome B-Grade Items"

    def calculate_weights(self):
        if self.b_grade_yarn_id and self.cones > 0:
            bg = self.b_grade_yarn
            # If batch has cones and weight, calculate proportionally
            if bg.cones > 0 and bg.weight_kg > 0:
                avg_weight_per_cone = Decimal(str(bg.weight_kg)) / Decimal(str(bg.cones))
                self.weight_kg = (Decimal(str(self.cones)) * avg_weight_per_cone).quantize(Decimal("0.000001"))
            elif bg.weight_kg > 0 and self.cones == bg.cones:
                self.weight_kg = Decimal(str(bg.weight_kg))
        self.weight_lb = (Decimal(str(self.weight_kg or 0)) * LB_PER_KG).quantize(Decimal("0.000001"))

    def save(self, *args, **kwargs):
        if not self.weight_kg:
            self.calculate_weights()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Outcome #{self.yarn_outcome_id} -> B-Grade #{self.b_grade_yarn_id} ({self.cones} cones)"



