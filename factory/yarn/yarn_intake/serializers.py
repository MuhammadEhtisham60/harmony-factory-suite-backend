"""
Serializers for YarnIntake (with nested YarnOutcome) and YarnOutcome.

Read-only calculated fields (backend computes, frontend must not submit):
  YarnIntake:  total_cones, total_rate, net_weight_kg, net_weight_lb,
               outcome_bags, outcome_weight_kg, outcome_weight_lb,
               remaining_bags, remaining_weight_kg, remaining_weight_lb
  YarnOutcome: outcome_weight_kg, outcome_weight_lb
"""

from decimal import Decimal

from rest_framework import serializers

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.yarn.sizing.models import Sizing
from .models import YarnIntake, YarnOutcome


# ── Supplier mini-repr ─────────────────────────────────────────────────────

class SupplierMinSerializer(serializers.ModelSerializer):
    supplierCode = serializers.CharField(source="supplier_code", read_only=True)
    supplierName = serializers.CharField(source="supplier_name", read_only=True)

    class Meta:
        model = Supplier
        fields = ["id", "supplierCode", "supplierName"]


# ── YarnBuyer mini-repr ────────────────────────────────────────────────────

class YarnBuyerMinSerializer(serializers.ModelSerializer):
    buyerName = serializers.CharField(source="buyer_name", read_only=True)

    class Meta:
        model = YarnBuyer
        fields = ["id", "buyerName"]


# ── Sizing mini-repr ───────────────────────────────────────────────────────

class SizingMinSerializer(serializers.ModelSerializer):
    sizingName = serializers.CharField(source="sizing_name", read_only=True)
    contactPerson = serializers.CharField(source="contact_person", read_only=True)

    class Meta:
        model = Sizing
        fields = ["id", "sizingName", "contactPerson"]


# ── YarnOutcome ────────────────────────────────────────────────────────────

class YarnOutcomeSerializer(serializers.ModelSerializer):
    """
    Writable serializer for YarnOutcome CRUD.

    Frontend provides:
        yarn_intake (id), outcome_type, outcome_bags, outcome_cones_per_bag,
        outcome_weight_per_bag_kg, yarn_buyer (id|null), total_price,
        outcome_date, notes

    Backend calculates:
        outcome_weight_kg = outcome_bags * outcome_weight_per_bag_kg
        outcome_weight_lb = outcome_weight_kg * 2.20462262
    """

    # ── Writable FKs ──────────────────────────────────────────────────────
    yarnIntake = serializers.PrimaryKeyRelatedField(
        source="yarn_intake",
        queryset=YarnIntake.objects.all()
    )
    yarnBuyer = serializers.PrimaryKeyRelatedField(
        source="yarn_buyer",
        queryset=YarnBuyer.objects.all(),
        required=False,
        allow_null=True
    )
    sizing = serializers.PrimaryKeyRelatedField(
        queryset=Sizing.objects.all(),
        required=False,
        allow_null=True
    )

    # ── Writable input fields ─────────────────────────────────────────────
    outcomeType = serializers.ChoiceField(
        source="outcome_type",
        choices=YarnOutcome.OutcomeTypeChoices.choices,
        required=False
    )
    outcomeBags = serializers.IntegerField(source="outcome_bags", min_value=0)
    outcomeConesPerBag = serializers.IntegerField(
        source="outcome_cones_per_bag", required=False, default=0
    )
    outcomeWeightPerBagKg = serializers.DecimalField(
        source="outcome_weight_per_bag_kg",
        max_digits=12, decimal_places=3
    )
    totalPrice = serializers.DecimalField(
        source="total_price",
        max_digits=15, decimal_places=2,
        required=False, default=0
    )
    outcomeDate = serializers.DateField(source="outcome_date")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    # ── Read-only calculated ──────────────────────────────────────────────
    outcomeWeightKg = serializers.DecimalField(
        source="outcome_weight_kg", max_digits=15, decimal_places=3, read_only=True
    )
    outcomeWeightLb = serializers.DecimalField(
        source="outcome_weight_lb", max_digits=15, decimal_places=3, read_only=True
    )

    # ── Audit ─────────────────────────────────────────────────────────────
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    # ── Nested display ────────────────────────────────────────────────────
    yarnBuyerDetail = serializers.SerializerMethodField()
    sizingDetail = serializers.SerializerMethodField()

    class Meta:
        model = YarnOutcome
        fields = [
            "id",
            "yarnIntake",
            "outcomeType",
            "outcomeBags",
            "outcomeConesPerBag",
            "outcomeWeightPerBagKg",
            "outcomeWeightKg",
            "outcomeWeightLb",
            "yarnBuyer",
            "yarnBuyerDetail",
            "sizing",
            "sizingDetail",
            "totalPrice",
            "outcomeDate",
            "notes",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id", "outcomeWeightKg", "outcomeWeightLb",
            "createdAt", "updatedAt", "createdBy", "updatedBy",
            "yarnBuyerDetail", "sizingDetail",
        ]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def get_yarnBuyerDetail(self, obj):
        if obj.yarn_buyer:
            return YarnBuyerMinSerializer(obj.yarn_buyer).data
        return None

    def get_sizingDetail(self, obj):
        if obj.sizing:
            return SizingMinSerializer(obj.sizing).data
        return None

    # ── Validation ────────────────────────────────────────────────────────

    def validate(self, attrs):
        outcome_type = attrs.get(
            "outcome_type",
            self.instance.outcome_type if self.instance else YarnOutcome.OutcomeTypeChoices.SIZING
        )
        yarn_buyer = attrs.get(
            "yarn_buyer",
            getattr(self.instance, "yarn_buyer", None) if self.instance else None
        )
        total_price = attrs.get(
            "total_price",
            getattr(self.instance, "total_price", Decimal("0")) if self.instance else Decimal("0")
        )
        sizing = attrs.get(
            "sizing",
            getattr(self.instance, "sizing", None) if self.instance else None
        )

        if outcome_type == YarnOutcome.OutcomeTypeChoices.SOLD:
            if not yarn_buyer:
                raise serializers.ValidationError({
                    "yarnBuyer": ["Yarn buyer is required for Sold outcome type."]
                })
            if not total_price or Decimal(str(total_price)) <= Decimal("0"):
                raise serializers.ValidationError({
                    "totalPrice": ["Total price must be greater than 0 for Sold outcome type."]
                })
            if sizing:
                raise serializers.ValidationError({
                    "sizing": ["Sizing must be null for Sold outcome type."]
                })

        elif outcome_type == YarnOutcome.OutcomeTypeChoices.WEFT:
            if yarn_buyer:
                raise serializers.ValidationError({
                    "yarnBuyer": ["Yarn buyer must be null for Weft outcome type."]
                })
            if total_price and Decimal(str(total_price)) > Decimal("0"):
                raise serializers.ValidationError({
                    "totalPrice": ["Total price must be 0 for Weft outcome type."]
                })
            if sizing:
                raise serializers.ValidationError({
                    "sizing": ["Sizing must be null for Weft outcome type."]
                })

        else:  # Sizing
            if yarn_buyer:
                raise serializers.ValidationError({
                    "yarnBuyer": ["Yarn buyer must be null for Sizing outcome type."]
                })
            if total_price and Decimal(str(total_price)) > Decimal("0"):
                raise serializers.ValidationError({
                    "totalPrice": ["Total price must be 0 for Sizing outcome type."]
                })
            if not sizing:
                raise serializers.ValidationError({
                    "sizing": ["Sizing reference is required for Sizing outcome type."]
                })

        outcome_bags = attrs.get(
            "outcome_bags",
            getattr(self.instance, "outcome_bags", 0) if self.instance else 0
        )
        if outcome_bags <= 0:
            raise serializers.ValidationError({
                "outcomeBags": ["Outcome bags must be greater than 0."]
            })

        return attrs


# ── YarnIntake (list) ──────────────────────────────────────────────────────

class YarnIntakeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list/table views.
    Does NOT include nested outcomes (too heavy for lists).
    """
    yarnName = serializers.CharField(source="yarn_name")
    yarnType = serializers.CharField(source="yarn_type")
    yarnCount = serializers.CharField(source="yarn_count")
    setNo = serializers.CharField(source="set_no")
    intakeDate = serializers.DateField(source="intake_date")
    supplierDetail = serializers.SerializerMethodField()
    productionType = serializers.CharField(source="production_type", read_only=True)

    # Intake totals
    conesPerBag = serializers.IntegerField(source="cones_per_bag")
    totalCones = serializers.IntegerField(source="total_cones", read_only=True)
    ratePerBag = serializers.DecimalField(source="rate_per_bag", max_digits=15, decimal_places=2)
    totalRate = serializers.DecimalField(source="total_rate", max_digits=15, decimal_places=2, read_only=True)
    weightPerBagKg = serializers.DecimalField(source="weight_per_bag_kg", max_digits=12, decimal_places=3)
    netWeightKg = serializers.DecimalField(source="net_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    netWeightLb = serializers.DecimalField(source="net_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    # Outcome summary
    outcomeBags = serializers.IntegerField(source="outcome_bags", read_only=True)
    outcomeWeightKg = serializers.DecimalField(source="outcome_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    outcomeWeightLb = serializers.DecimalField(source="outcome_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    # Remaining
    remainingBags = serializers.IntegerField(source="remaining_bags", read_only=True)
    remainingWeightKg = serializers.DecimalField(source="remaining_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    remainingWeightLb = serializers.DecimalField(source="remaining_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = YarnIntake
        fields = [
            "id", "yarnName", "yarnType", "yarnCount", "setNo",
            "intakeDate", "supplierDetail", "productionType",
            "bags", "conesPerBag", "totalCones",
            "ratePerBag", "totalRate",
            "weightPerBagKg", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "remainingBags", "remainingWeightKg", "remainingWeightLb",
            "createdBy", "updatedBy", "createdAt", "updatedAt",
        ]

    def get_supplierDetail(self, obj):
        if obj.supplier:
            return SupplierMinSerializer(obj.supplier).data
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None


# ── YarnIntake (detail) ────────────────────────────────────────────────────

class YarnIntakeDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create / retrieve / update.
    Includes nested read-only outcomes for GET detail.

    Frontend provides:
        yarn_name, yarn_type, yarn_count, set_no, intake_date, supplier (id),
        production_type, bags, cones_per_bag, rate_per_bag, weight_per_bag_kg

    Backend calculates (read-only, ignored if submitted):
        total_cones, total_rate, net_weight_kg, net_weight_lb,
        outcome_bags, outcome_weight_kg, outcome_weight_lb,
        remaining_bags, remaining_weight_kg, remaining_weight_lb
    """
    # ── Writable fields ───────────────────────────────────────────────────
    yarnName = serializers.CharField(source="yarn_name")
    yarnType = serializers.CharField(source="yarn_type")
    yarnCount = serializers.CharField(source="yarn_count")
    setNo = serializers.CharField(source="set_no")
    intakeDate = serializers.DateField(source="intake_date")
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    productionType = serializers.CharField(
        source="production_type", required=False, allow_blank=True, default=""
    )
    bags = serializers.IntegerField(min_value=1)
    conesPerBag = serializers.IntegerField(source="cones_per_bag", min_value=0, default=0)
    ratePerBag = serializers.DecimalField(
        source="rate_per_bag", max_digits=15, decimal_places=2, default=0
    )
    weightPerBagKg = serializers.DecimalField(
        source="weight_per_bag_kg", max_digits=12, decimal_places=3
    )

    # ── Read-only calculated ──────────────────────────────────────────────
    totalCones = serializers.IntegerField(source="total_cones", read_only=True)
    totalRate = serializers.DecimalField(source="total_rate", max_digits=15, decimal_places=2, read_only=True)
    netWeightKg = serializers.DecimalField(source="net_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    netWeightLb = serializers.DecimalField(source="net_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    outcomeBags = serializers.IntegerField(source="outcome_bags", read_only=True)
    outcomeWeightKg = serializers.DecimalField(source="outcome_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    outcomeWeightLb = serializers.DecimalField(source="outcome_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    remainingBags = serializers.IntegerField(source="remaining_bags", read_only=True)
    remainingWeightKg = serializers.DecimalField(source="remaining_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    remainingWeightLb = serializers.DecimalField(source="remaining_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    # ── Nested outcomes (read-only, for GET detail) ───────────────────────
    outcomes = YarnOutcomeSerializer(many=True, read_only=True)

    # ── Supplier display ──────────────────────────────────────────────────
    supplierDetail = serializers.SerializerMethodField()

    # ── Audit ─────────────────────────────────────────────────────────────
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = YarnIntake
        fields = [
            "id",
            "yarnName", "yarnType", "yarnCount", "setNo",
            "intakeDate", "supplier", "supplierDetail", "productionType",
            "bags", "conesPerBag", "totalCones",
            "ratePerBag", "totalRate",
            "weightPerBagKg", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "remainingBags", "remainingWeightKg", "remainingWeightLb",
            "outcomes",
            "createdBy", "updatedBy", "createdAt", "updatedAt",
        ]
        read_only_fields = [
            "id",
            "totalCones", "totalRate", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "remainingBags", "remainingWeightKg", "remainingWeightLb",
            "outcomes", "supplierDetail",
            "createdAt", "updatedAt", "createdBy", "updatedBy",
        ]

    def get_supplierDetail(self, obj):
        if obj.supplier:
            return SupplierMinSerializer(obj.supplier).data
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        intake = YarnIntake(**validated_data)
        intake.calculate_intake_fields()
        intake.init_remaining_stock()
        intake.save()
        return intake

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.calculate_intake_fields()

        # Recalculate remaining based on current outcome summary
        from .services import recalculate_yarn_intake_stock
        instance.save()
        recalculate_yarn_intake_stock(instance)
        # Refresh from DB to get updated summary fields
        instance.refresh_from_db()
        return instance
