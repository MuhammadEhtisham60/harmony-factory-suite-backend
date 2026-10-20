"""
Serializers for YarnIntake (with nested YarnOutcome) and YarnOutcome.

Read-only calculated fields (backend computes, frontend must not submit):
  YarnIntake:  total_cones, total_rate, net_weight_kg, net_weight_lb,
               outcome_bags, outcome_weight_kg, outcome_weight_lb,
               remaining_bags, remaining_weight_kg, remaining_weight_lb
  YarnOutcome: outcome_weight_kg, outcome_weight_lb
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.yarn.sizing.models import Sizing
from factory.yarn.yarn_stock.models import YarnStock, LB_PER_KG
from factory.yarn.yarn_stock.serializers import YarnStockMinSerializer
from .models import YarnIntake, YarnOutcome, YarnOutcomeItem


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


# ── YarnOutcomeItem ────────────────────────────────────────────────────────

class YarnOutcomeItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual yarn intake batch items within a YarnOutcome dispatch.
    """
    yarnIntake = serializers.PrimaryKeyRelatedField(
        source="yarn_intake",
        queryset=YarnIntake.objects.all(),
        required=False,
    )
    yarnIntakeId = serializers.IntegerField(
        write_only=True,
        required=False,
    )
    bags = serializers.IntegerField(min_value=1)
    conesPerBag = serializers.IntegerField(
        source="cones_per_bag", required=False, default=0
    )
    weightPerBagKg = serializers.DecimalField(
        source="weight_per_bag_kg",
        max_digits=12,
        decimal_places=6,
        required=False,
    )
    weightKg = serializers.DecimalField(
        source="weight_kg", max_digits=15, decimal_places=6, read_only=True
    )
    weightLb = serializers.DecimalField(
        source="weight_lb", max_digits=15, decimal_places=6, read_only=True
    )
    yarnIntakeDetail = serializers.SerializerMethodField()

    class Meta:
        model = YarnOutcomeItem
        fields = [
            "id",
            "yarnIntake",
            "yarnIntakeId",
            "bags",
            "conesPerBag",
            "weightPerBagKg",
            "weightKg",
            "weightLb",
            "yarnIntakeDetail",
        ]
        read_only_fields = ["id", "weightKg", "weightLb", "yarnIntakeDetail"]

    def get_yarnIntakeDetail(self, obj):
        if obj.yarn_intake:
            return {
                "id": obj.yarn_intake.id,
                "setNo": obj.yarn_intake.set_no,
                "supplierName": obj.yarn_intake.supplier.supplier_name if obj.yarn_intake.supplier else "",
                "remainingBags": obj.yarn_intake.remaining_bags,
                "weightPerBagKg": str(obj.yarn_intake.weight_per_bag_kg),
            }
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if "yarn_intake" in data and "yarnIntake" not in data:
            data["yarnIntake"] = data["yarn_intake"]
        if "yarn_intake_id" in data and "yarnIntakeId" not in data:
            data["yarnIntakeId"] = data["yarn_intake_id"]
        if "outcome_bags" in data and "bags" not in data:
            data["bags"] = data["outcome_bags"]
        if "outcomeBags" in data and "bags" not in data:
            data["bags"] = data["outcomeBags"]
        if "cones_per_bag" in data and "conesPerBag" not in data:
            data["conesPerBag"] = data["cones_per_bag"]
        if "outcome_cones_per_bag" in data and "conesPerBag" not in data:
            data["conesPerBag"] = data["outcome_cones_per_bag"]
        if "outcomeConesPerBag" in data and "conesPerBag" not in data:
            data["conesPerBag"] = data["outcomeConesPerBag"]
        if "weight_per_bag_kg" in data and "weightPerBagKg" not in data:
            data["weightPerBagKg"] = data["weight_per_bag_kg"]
        if "outcome_weight_per_bag_kg" in data and "weightPerBagKg" not in data:
            data["weightPerBagKg"] = data["outcome_weight_per_bag_kg"]
        if "outcomeWeightPerBagKg" in data and "weightPerBagKg" not in data:
            data["weightPerBagKg"] = data["outcomeWeightPerBagKg"]
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret["yarn_intake"] = instance.yarn_intake_id
        ret["yarn_intake_id"] = instance.yarn_intake_id
        ret["outcome_bags"] = instance.bags
        ret["outcomeBags"] = instance.bags
        ret["weight_per_bag_kg"] = str(instance.weight_per_bag_kg)
        ret["weight_kg"] = str(instance.weight_kg)
        ret["weight_lb"] = str(instance.weight_lb)
        return ret


# ── YarnOutcome ────────────────────────────────────────────────────────────

class YarnOutcomeSerializer(serializers.ModelSerializer):
    """
    Writable serializer for YarnOutcome CRUD.

    Dispatches yarn from one or more YarnIntake batches.
    Dispatching directly from stock pool without specifying intake batches is disallowed.

    Frontend provides:
        intakes (list of {yarn_intake, bags, ...}), OR single yarn_intake / yarnIntake
        outcome_type, yarn_buyer (id|null), total_price, outcome_date, notes

    Backend calculates:
        outcome_bags, outcome_weight_kg, outcome_weight_lb, outcome_weight_per_bag_kg,
        stock (resolved from contributing intakes)
    """

    # ── Writable FKs ──────────────────────────────────────────────────────
    stock = serializers.PrimaryKeyRelatedField(
        queryset=YarnStock.objects.all(),
        required=False,
        allow_null=True
    )
    stockId = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True
    )
    yarnIntake = serializers.PrimaryKeyRelatedField(
        queryset=YarnIntake.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    yarnIntakeId = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True
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
    outcomeBags = serializers.IntegerField(source="outcome_bags", min_value=0, required=False)
    outcomeConesPerBag = serializers.IntegerField(
        source="outcome_cones_per_bag", required=False, default=0
    )
    outcomeWeightPerBagKg = serializers.DecimalField(
        source="outcome_weight_per_bag_kg",
        max_digits=12, decimal_places=6,
        required=False
    )
    totalPrice = serializers.DecimalField(
        source="total_price",
        max_digits=15, decimal_places=6,
        required=False, default=0
    )
    ratePerKg = serializers.DecimalField(
        max_digits=15, decimal_places=6, required=False, allow_null=True
    )
    outcomeDate = serializers.DateField(source="outcome_date")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    # ── Multi-intake breakdown ────────────────────────────────────────────
    intakes = YarnOutcomeItemSerializer(source="items", many=True, read_only=True)
    items = YarnOutcomeItemSerializer(many=True, read_only=True)
    intakeSetNumbers = serializers.SerializerMethodField()
    intakeSetNoDisplay = serializers.SerializerMethodField()

    yarnName = serializers.SerializerMethodField()
    yarnType = serializers.SerializerMethodField()
    yarnCount = serializers.SerializerMethodField()
    yarnIntakeDetail = serializers.SerializerMethodField()

    # ── Beam Assignment inputs (optional at creation) ─────────────────────
    beamIds = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )
    beamId = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )
    beam = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )

    # ── Read-only calculated ──────────────────────────────────────────────
    outcomeWeightKg = serializers.DecimalField(
        source="outcome_weight_kg", max_digits=15, decimal_places=6, read_only=True
    )
    outcomeWeightLb = serializers.DecimalField(
        source="outcome_weight_lb", max_digits=15, decimal_places=6, read_only=True
    )
    beamAssignments = serializers.SerializerMethodField()
    totalBeams = serializers.IntegerField(source="total_beams", read_only=True)
    status = serializers.SerializerMethodField()
    sizingOutcome = serializers.SerializerMethodField()
    isReceived = serializers.SerializerMethodField()
    isPartiallyReceived = serializers.SerializerMethodField()

    # ── Audit ─────────────────────────────────────────────────────────────
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    # ── Nested display ────────────────────────────────────────────────────
    stockDetail = serializers.SerializerMethodField()
    yarnBuyerDetail = serializers.SerializerMethodField()
    sizingDetail = serializers.SerializerMethodField()

    class Meta:
        model = YarnOutcome
        fields = [
            "id",
            "stock",
            "stockId",
            "stockDetail",
            "yarnIntake",
            "yarnIntakeId",
            "yarnIntakeDetail",
            "intakes",
            "items",
            "intakeSetNumbers",
            "intakeSetNoDisplay",
            "yarnName",
            "yarnType",
            "yarnCount",
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
            "ratePerKg",
            "status",
            "sizingOutcome",
            "isReceived",
            "isPartiallyReceived",
            "outcomeDate",
            "notes",
            "beamIds",
            "beamId",
            "beam",
            "beamAssignments",
            "totalBeams",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id", "outcomeWeightKg", "outcomeWeightLb",
            "intakes", "items", "intakeSetNumbers", "intakeSetNoDisplay",
            "yarnName", "yarnType", "yarnCount", "yarnIntakeDetail",
            "beamAssignments", "totalBeams", "status", "sizingOutcome", "isReceived", "isPartiallyReceived",
            "createdAt", "updatedAt", "createdBy", "updatedBy",
            "stockDetail", "yarnBuyerDetail", "sizingDetail",
        ]

    def get_stockDetail(self, obj):
        if obj.stock:
            return YarnStockMinSerializer(obj.stock).data
        return None

    def get_beamAssignments(self, obj):
        if hasattr(obj, "beam_assignments"):
            from factory.yarn.sizing.serializers import SizingBeamAssignmentSerializer
            return SizingBeamAssignmentSerializer(
                obj.beam_assignments.all(), many=True, context=self.context
            ).data
        return []

    def get_status(self, obj):
        if obj.outcome_type == YarnOutcome.OutcomeTypeChoices.SIZING:
            if hasattr(obj, "sizing_outcomes") and obj.sizing_outcomes.exists():
                from factory.yarn.sizing.services import sync_yarn_outcome_status
                return sync_yarn_outcome_status(obj)
            return getattr(obj, "status", None) or YarnOutcome.StatusChoices.IN_SIZING
        return getattr(obj, "status", None) or "Dispatched"

    def get_isReceived(self, obj):
        return self.get_status(obj) == YarnOutcome.StatusChoices.RECEIVED

    def get_isPartiallyReceived(self, obj):
        return self.get_status(obj) == YarnOutcome.StatusChoices.PARTIALLY_RECEIVED

    def get_sizingOutcome(self, obj):
        if hasattr(obj, "sizing_outcomes"):
            so = obj.sizing_outcomes.order_by("-id").first()
            if so:
                return {
                    "id": so.id,
                    "setNo": so.set_no,
                    "setBill": so.set_bill,
                    "ratePerKg": str(so.rate_per_kg) if so.rate_per_kg is not None else None,
                    "totalRate": str(so.total_rate) if so.total_rate is not None else None,
                    "netWeightKg": str(so.net_weight_kg) if so.net_weight_kg is not None else None,
                    "returnBags": str(so.return_bags) if so.return_bags is not None else "0.000000",
                    "return_bags": str(so.return_bags) if so.return_bags is not None else "0.000000",
                    "returnCones": str(so.return_cones) if so.return_cones is not None else "0.000000",
                    "return_cones": str(so.return_cones) if so.return_cones is not None else "0.000000",
                    "outcomeDate": so.outcome_date,
                    "amountPaid": str(so.amount_paid) if so.amount_paid is not None else "0.000000",
                    "amountDue": str(so.amount_due) if so.amount_due is not None else "0.000000",
                    "paymentStatus": so.payment_status or "Unpaid",
                }
        return None

    def get_intakeSetNumbers(self, obj):
        set_nos = [item.yarn_intake.set_no for item in obj.items.all() if item.yarn_intake and item.yarn_intake.set_no]
        if not set_nos and obj.primary_intake and obj.primary_intake.set_no:
            set_nos = [obj.primary_intake.set_no]
        return list(dict.fromkeys(set_nos))

    def get_intakeSetNoDisplay(self, obj):
        nums = self.get_intakeSetNumbers(obj)
        return ", ".join(nums) if nums else ""

    def get_yarnName(self, obj):
        pi = obj.primary_intake
        stock = obj.stock or (pi.stock if pi else None)
        return stock.yarn_name.name if stock and stock.yarn_name else ""

    def get_yarnType(self, obj):
        pi = obj.primary_intake
        stock = obj.stock or (pi.stock if pi else None)
        return stock.yarn_type.name if stock and stock.yarn_type else ""

    def get_yarnCount(self, obj):
        pi = obj.primary_intake
        stock = obj.stock or (pi.stock if pi else None)
        return stock.yarn_count.name if stock and stock.yarn_count else ""

    def get_yarnIntakeDetail(self, obj):
        pi = obj.primary_intake
        if pi:
            return {
                "id": pi.id,
                "setNo": pi.set_no,
                "remainingBags": pi.remaining_bags,
                "weightPerBagKg": str(pi.weight_per_bag_kg),
            }
        return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        primary_intake = instance.primary_intake
        if instance.stock:
            ret["stock"] = instance.stock_id
            ret["stockId"] = instance.stock_id
            if instance.stock.yarn_name:
                ret["yarnName"] = instance.stock.yarn_name.name
            if instance.stock.yarn_type:
                ret["yarnType"] = instance.stock.yarn_type.name
            if instance.stock.yarn_count:
                ret["yarnCount"] = instance.stock.yarn_count.name
        elif primary_intake and primary_intake.stock:
            stock = primary_intake.stock
            ret["stock"] = stock.id
            ret["stockId"] = stock.id
            if stock.yarn_name:
                ret["yarnName"] = stock.yarn_name.name
            if stock.yarn_type:
                ret["yarnType"] = stock.yarn_type.name
            if stock.yarn_count:
                ret["yarnCount"] = stock.yarn_count.name

        if primary_intake:
            ret["yarnIntake"] = primary_intake.id
            ret["yarnIntakeId"] = primary_intake.id
            ret["yarnIntakeDetail"] = {
                "id": primary_intake.id,
                "setNo": primary_intake.set_no,
                "remainingBags": primary_intake.remaining_bags,
                "weightPerBagKg": str(primary_intake.weight_per_bag_kg),
            }

        items_qs = instance.items.all().select_related("yarn_intake", "yarn_intake__supplier")
        items_data = YarnOutcomeItemSerializer(items_qs, many=True, context=self.context).data
        ret["intakes"] = items_data
        ret["items"] = items_data

        set_nos = [item.yarn_intake.set_no for item in items_qs if item.yarn_intake and item.yarn_intake.set_no]
        if not set_nos and primary_intake and primary_intake.set_no:
            set_nos = [primary_intake.set_no]
        ret["intakeSetNumbers"] = list(dict.fromkeys(set_nos))
        ret["intakeSetNoDisplay"] = ", ".join(list(dict.fromkeys(set_nos))) if set_nos else ""

        if hasattr(instance, "sizing_outcomes") and instance.sizing_outcomes.exists():
            so = instance.sizing_outcomes.order_by("-id").first()
            if so:
                if so.rate_per_kg is not None and so.rate_per_kg > 0:
                    ret["ratePerKg"] = str(so.rate_per_kg)
                if so.total_rate is not None and so.total_rate > 0:
                    ret["totalPrice"] = str(so.total_rate)
                    ret["totalRate"] = str(so.total_rate)
                ret["amountPaid"] = str(so.amount_paid) if so.amount_paid is not None else "0.000000"
                ret["amountDue"] = str(so.amount_due) if so.amount_due is not None else "0.000000"
                ret["paymentStatus"] = so.payment_status or "Unpaid"
        return ret

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
        raw_items = (
            self.initial_data.get("intakes")
            or self.initial_data.get("items")
            or self.initial_data.get("yarn_intakes")
            or self.initial_data.get("yarnIntakes")
        )

        parsed_items = []
        if raw_items is not None:
            if not isinstance(raw_items, (list, tuple)) or len(raw_items) == 0:
                raise serializers.ValidationError({
                    "intakes": ["At least one intake item must be specified."]
                })

            for idx, item in enumerate(raw_items):
                if not isinstance(item, dict):
                    raise serializers.ValidationError({
                        "intakes": [f"Item at position {idx} must be an object."]
                    })
                raw_intake_id = (
                    item.get("yarnIntake")
                    or item.get("yarn_intake")
                    or item.get("yarnIntakeId")
                    or item.get("yarn_intake_id")
                    or item.get("intake")
                    or item.get("intakeId")
                    or item.get("intake_id")
                    or item.get("id")
                )
                if not raw_intake_id:
                    raise serializers.ValidationError({
                        "intakes": [f"Intake reference is required for item at position {idx}."]
                    })
                try:
                    intake_obj = YarnIntake.objects.get(pk=raw_intake_id) if not isinstance(raw_intake_id, YarnIntake) else raw_intake_id
                except (YarnIntake.DoesNotExist, ValueError):
                    raise serializers.ValidationError({
                        "intakes": [f"Invalid yarn intake ID '{raw_intake_id}' at position {idx}."]
                    })

                raw_bags = (
                    item.get("bags")
                    or item.get("outcomeBags")
                    or item.get("outcome_bags")
                    or item.get("quantity")
                )
                if raw_bags is None:
                    raise serializers.ValidationError({
                        "intakes": [f"Bags count is required for intake '{intake_obj.set_no or intake_obj.id}'."]
                    })
                try:
                    bags_val = int(raw_bags)
                    if bags_val <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        "intakes": [f"Bags must be a positive integer for intake '{intake_obj.set_no or intake_obj.id}'."]
                    })

                raw_cones = (
                    item.get("conesPerBag")
                    or item.get("cones_per_bag")
                    or item.get("outcomeConesPerBag")
                    or item.get("outcome_cones_per_bag")
                )
                cones_val = int(raw_cones) if raw_cones is not None and str(raw_cones).isdigit() else intake_obj.cones_per_bag

                raw_wpb = (
                    item.get("weightPerBagKg")
                    or item.get("weight_per_bag_kg")
                    or item.get("outcomeWeightPerBagKg")
                    or item.get("outcome_weight_per_bag_kg")
                )
                wpb_val = Decimal(str(raw_wpb)) if raw_wpb is not None and str(raw_wpb).strip() else intake_obj.weight_per_bag_kg

                parsed_items.append({
                    "intake": intake_obj,
                    "bags": bags_val,
                    "cones_per_bag": cones_val,
                    "weight_per_bag_kg": wpb_val,
                })

        else:
            intake_val = attrs.get("yarnIntake") or attrs.get("yarn_intake")
            raw_intake = (
                self.initial_data.get("yarnIntakeId")
                or self.initial_data.get("yarn_intake_id")
                or self.initial_data.get("yarnIntake")
                or self.initial_data.get("yarn_intake")
            )
            if not intake_val and raw_intake:
                try:
                    intake_val = YarnIntake.objects.get(pk=raw_intake)
                except (YarnIntake.DoesNotExist, ValueError):
                    raise serializers.ValidationError({"yarnIntake": ["Invalid yarn intake ID."]})

            if intake_val:
                outcome_bags = attrs.get(
                    "outcome_bags",
                    self.initial_data.get("outcomeBags", self.initial_data.get("outcome_bags"))
                )
                if not outcome_bags:
                    raise serializers.ValidationError({"outcomeBags": ["Outcome bags must be greater than 0."]})
                try:
                    outcome_bags = int(outcome_bags)
                    if outcome_bags <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise serializers.ValidationError({"outcomeBags": ["Outcome bags must be greater than 0."]})

                cones_val = attrs.get("outcome_cones_per_bag") or intake_val.cones_per_bag
                wpb_val = attrs.get("outcome_weight_per_bag_kg") or intake_val.weight_per_bag_kg

                parsed_items.append({
                    "intake": intake_val,
                    "bags": outcome_bags,
                    "cones_per_bag": cones_val,
                    "weight_per_bag_kg": wpb_val,
                })
            else:
                if not self.instance:
                    raise serializers.ValidationError({
                        "yarnIntake": [
                            "Yarn dispatch must be from one or more yarn intake batches. "
                            "Dispatching directly from stock pool is not allowed."
                        ]
                    })
                parsed_items = None

        if parsed_items is not None:
            from collections import defaultdict
            bags_per_intake = defaultdict(int)
            for item in parsed_items:
                bags_per_intake[item["intake"].id] += item["bags"]

            first_intake = parsed_items[0]["intake"]
            first_stock = first_intake.stock

            for item in parsed_items:
                intake = item["intake"]
                if intake.stock_id != first_stock.id:
                    if (
                        intake.yarn_name_id != first_intake.yarn_name_id
                        or intake.yarn_type_id != first_intake.yarn_type_id
                        or intake.yarn_count_id != first_intake.yarn_count_id
                    ):
                        raise serializers.ValidationError({
                            "intakes": [
                                f"All selected yarn intakes must share the same yarn name, type, and count. "
                                f"Intake '{intake.set_no}' ({intake.yarn_name}) differs from '{first_intake.set_no}' ({first_intake.yarn_name})."
                            ]
                        })

            for intake_id, total_requested in bags_per_intake.items():
                intake = YarnIntake.objects.get(pk=intake_id)
                available = intake.remaining_bags
                if self.instance:
                    prev_item_bags = self.instance.items.filter(yarn_intake=intake).aggregate(s=Sum("bags"))["s"] or 0
                    available += prev_item_bags

                if total_requested > available:
                    err_field = "intakes" if raw_items is not None else "outcomeBags"
                    raise serializers.ValidationError({
                        err_field: [
                            f"Yarn intake batch '{intake.set_no or intake.id}' only has {available} bags remaining. "
                            f"Cannot dispatch {total_requested} bags."
                        ]
                    })

            total_bags = sum(it["bags"] for it in parsed_items)
            total_kg = sum(Decimal(str(it["bags"])) * Decimal(str(it["weight_per_bag_kg"])) for it in parsed_items)
            avg_wpb = (total_kg / Decimal(str(total_bags))).quantize(Decimal("0.000001")) if total_bags > 0 else Decimal("0")
            avg_cones = parsed_items[0]["cones_per_bag"]

            attrs["outcome_bags"] = total_bags
            attrs["outcome_weight_per_bag_kg"] = avg_wpb
            attrs["outcome_cones_per_bag"] = avg_cones
            attrs["stock"] = first_stock
            attrs["_parsed_items"] = parsed_items

        attrs.pop("yarn_intake", None)
        attrs.pop("yarnIntake", None)
        attrs.pop("yarnIntakeId", None)

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

    def create(self, validated_data):
        items_data = validated_data.pop("_parsed_items", [])
        validated_data.pop("yarn_intake", None)
        validated_data.pop("yarnIntake", None)
        validated_data.pop("yarnIntakeId", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beamId", None)
        validated_data.pop("beam", None)
        validated_data.pop("ratePerKg", None)
        validated_data.pop("stockId", None)

        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None
        if user:
            validated_data["created_by"] = user
            validated_data["updated_by"] = user

        with transaction.atomic():
            outcome = YarnOutcome(**validated_data)
            outcome.save()

            intakes_to_recalc = set()
            for item in items_data:
                intake = item["intake"]
                YarnOutcomeItem.objects.create(
                    yarn_outcome=outcome,
                    yarn_intake=intake,
                    bags=item["bags"],
                    cones_per_bag=item["cones_per_bag"],
                    weight_per_bag_kg=item["weight_per_bag_kg"],
                )
                intakes_to_recalc.add(intake.id)

            outcome.calculate_outcome_fields()
            outcome.save()

            from .services import recalculate_yarn_intake_stock
            from factory.yarn.yarn_stock.services import recalculate_yarn_stock

            for intake_id in sorted(list(intakes_to_recalc)):
                locked_intake = YarnIntake.objects.select_for_update().get(pk=intake_id)
                recalculate_yarn_intake_stock(locked_intake)

            if outcome.stock_id:
                locked_stock = YarnStock.objects.select_for_update().get(pk=outcome.stock_id)
                recalculate_yarn_stock(locked_stock)

            return outcome

    def update(self, instance, validated_data):
        items_data = validated_data.pop("_parsed_items", None)
        validated_data.pop("yarn_intake", None)
        validated_data.pop("yarnIntake", None)
        validated_data.pop("yarnIntakeId", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beamId", None)
        validated_data.pop("beam", None)
        validated_data.pop("ratePerKg", None)
        validated_data.pop("stockId", None)

        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None
        if user:
            validated_data["updated_by"] = user

        with transaction.atomic():
            old_intake_ids = set()
            for item in instance.items.all():
                if item.yarn_intake_id:
                    old_intake_ids.add(item.yarn_intake_id)

            old_stock_id = instance.stock_id

            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            new_intake_ids = set()
            if items_data is not None:
                instance.items.all().delete()
                for item in items_data:
                    intake = item["intake"]
                    YarnOutcomeItem.objects.create(
                        yarn_outcome=instance,
                        yarn_intake=intake,
                        bags=item["bags"],
                        cones_per_bag=item["cones_per_bag"],
                        weight_per_bag_kg=item["weight_per_bag_kg"],
                    )
                    new_intake_ids.add(intake.id)
                instance.calculate_outcome_fields()
                instance.save()
            else:
                for item in instance.items.all():
                    if item.yarn_intake_id:
                        new_intake_ids.add(item.yarn_intake_id)

            from .services import recalculate_yarn_intake_stock
            from factory.yarn.yarn_stock.services import recalculate_yarn_stock

            all_intake_ids = old_intake_ids.union(new_intake_ids)
            for i_id in sorted(list(all_intake_ids)):
                locked_intake = YarnIntake.objects.select_for_update().get(pk=i_id)
                recalculate_yarn_intake_stock(locked_intake)

            all_stock_ids = {s for s in [old_stock_id, instance.stock_id] if s is not None}
            for s_id in sorted(list(all_stock_ids)):
                locked_stock = YarnStock.objects.select_for_update().get(pk=s_id)
                recalculate_yarn_stock(locked_stock)

            return instance


# ── YarnIntake (list) ──────────────────────────────────────────────────────

class YarnIntakeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list/table views.
    Does NOT include nested outcomes (too heavy for lists).
    """
    yarnName = serializers.SerializerMethodField()
    yarnType = serializers.SerializerMethodField()
    yarnCount = serializers.SerializerMethodField()
    yarnNameId = serializers.IntegerField(source="yarn_name_id", read_only=True)
    yarnTypeId = serializers.IntegerField(source="yarn_type_id", read_only=True)
    yarnCountId = serializers.IntegerField(source="yarn_count_id", read_only=True)
    yarnNameDetail = serializers.SerializerMethodField()
    yarnTypeDetail = serializers.SerializerMethodField()
    yarnCountDetail = serializers.SerializerMethodField()
    setNo = serializers.CharField(source="set_no")
    intakeDate = serializers.DateField(source="intake_date")
    supplierDetail = serializers.SerializerMethodField()
    stock = serializers.PrimaryKeyRelatedField(read_only=True)
    stockDetail = serializers.SerializerMethodField()
    productionType = serializers.CharField(source="production_type", read_only=True)

    # Intake totals
    conesPerBag = serializers.IntegerField(source="cones_per_bag")
    totalCones = serializers.IntegerField(source="total_cones", read_only=True)
    ratePerLb = serializers.DecimalField(source="rate_per_lb", max_digits=15, decimal_places=6, read_only=True)
    totalRate = serializers.DecimalField(source="total_rate", max_digits=15, decimal_places=6, read_only=True)
    weightPerBagKg = serializers.DecimalField(source="weight_per_bag_kg", max_digits=12, decimal_places=6)
    netWeightKg = serializers.DecimalField(source="net_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    netWeightLb = serializers.DecimalField(source="net_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    # Outcome summary
    outcomeBags = serializers.IntegerField(source="outcome_bags", read_only=True)
    outcomeWeightKg = serializers.DecimalField(source="outcome_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    outcomeWeightLb = serializers.DecimalField(source="outcome_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    # Returned from sizing summary
    returnBags = serializers.DecimalField(source="return_bags", max_digits=15, decimal_places=6, read_only=True)
    return_bags = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    returnCones = serializers.DecimalField(source="return_cones", max_digits=15, decimal_places=6, read_only=True)
    return_cones = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    # Remaining
    remainingBags = serializers.IntegerField(source="remaining_bags", read_only=True)
    remainingCones = serializers.IntegerField(source="remaining_cones", read_only=True)
    remaining_cones = serializers.IntegerField(read_only=True)
    remainingWeightKg = serializers.DecimalField(source="remaining_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    remainingWeightLb = serializers.DecimalField(source="remaining_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = YarnIntake
        fields = [
            "id", "yarnName", "yarnType", "yarnCount",
            "yarnNameId", "yarnTypeId", "yarnCountId",
            "yarnNameDetail", "yarnTypeDetail", "yarnCountDetail",
            "setNo",
            "intakeDate", "supplierDetail", "stock", "stockDetail", "productionType",
            "bags", "conesPerBag", "totalCones",
            "ratePerLb", "totalRate",
            "weightPerBagKg", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "returnBags", "return_bags", "returnCones", "return_cones",
            "remainingBags", "remainingCones", "remaining_cones", "remainingWeightKg", "remainingWeightLb",
            "createdBy", "updatedBy", "createdAt", "updatedAt",
        ]

    def get_yarnName(self, obj):
        return obj.yarn_name.name if obj.yarn_name else ""

    def get_yarnType(self, obj):
        return obj.yarn_type.name if obj.yarn_type else ""

    def get_yarnCount(self, obj):
        return obj.yarn_count.name if obj.yarn_count else ""

    def get_yarnNameDetail(self, obj):
        return {"id": obj.yarn_name.id, "name": obj.yarn_name.name} if obj.yarn_name else None

    def get_yarnTypeDetail(self, obj):
        return {"id": obj.yarn_type.id, "name": obj.yarn_type.name} if obj.yarn_type else None

    def get_yarnCountDetail(self, obj):
        return {"id": obj.yarn_count.id, "name": obj.yarn_count.name} if obj.yarn_count else None

    def get_stockDetail(self, obj):
        if obj.stock:
            return YarnStockMinSerializer(obj.stock).data
        return None

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
        production_type, bags, cones_per_bag, rate_per_lb, weight_per_bag_kg

    Backend calculates (read-only, ignored if submitted):
        total_cones, total_rate, net_weight_kg, net_weight_lb,
        outcome_bags, outcome_weight_kg, outcome_weight_lb,
        remaining_bags, remaining_weight_kg, remaining_weight_lb
    """
    # ── Writable fields ───────────────────────────────────────────────────
    yarn_name = serializers.PrimaryKeyRelatedField(
        queryset=YarnName.objects.all(), required=False
    )
    yarn_type = serializers.PrimaryKeyRelatedField(
        queryset=YarnType.objects.all(), required=False
    )
    yarn_count = serializers.PrimaryKeyRelatedField(
        queryset=YarnCount.objects.all(), required=False
    )
    yarnName = serializers.CharField(required=False, write_only=True)
    yarnType = serializers.CharField(required=False, write_only=True)
    yarnCount = serializers.CharField(required=False, write_only=True)
    yarnNameId = serializers.IntegerField(required=False, write_only=True)
    yarnTypeId = serializers.IntegerField(required=False, write_only=True)
    yarnCountId = serializers.IntegerField(required=False, write_only=True)
    setNo = serializers.CharField(
        source="set_no", required=False, allow_blank=True, default=""
    )
    intakeDate = serializers.DateField(source="intake_date")
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    productionType = serializers.CharField(
        source="production_type", required=False, allow_blank=True, default=""
    )
    bags = serializers.IntegerField(min_value=1)
    conesPerBag = serializers.IntegerField(source="cones_per_bag", min_value=0, default=0)
    ratePerLb = serializers.DecimalField(
        source="rate_per_lb", max_digits=15, decimal_places=6, default=Decimal("0.000000")
    )
    weightPerBagKg = serializers.DecimalField(
        source="weight_per_bag_kg", max_digits=12, decimal_places=6
    )

    # ── Read-only stock link ──────────────────────────────────────────────
    stock = serializers.PrimaryKeyRelatedField(read_only=True)
    stockDetail = serializers.SerializerMethodField()

    # ── Read-only calculated ──────────────────────────────────────────────
    totalCones = serializers.IntegerField(source="total_cones", read_only=True)
    totalRate = serializers.DecimalField(source="total_rate", max_digits=15, decimal_places=6, read_only=True)
    netWeightKg = serializers.DecimalField(source="net_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    netWeightLb = serializers.DecimalField(source="net_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    outcomeBags = serializers.IntegerField(source="outcome_bags", read_only=True)
    outcomeWeightKg = serializers.DecimalField(source="outcome_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    outcomeWeightLb = serializers.DecimalField(source="outcome_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    returnBags = serializers.DecimalField(source="return_bags", max_digits=15, decimal_places=6, read_only=True)
    return_bags = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    returnCones = serializers.DecimalField(source="return_cones", max_digits=15, decimal_places=6, read_only=True)
    return_cones = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    remainingBags = serializers.IntegerField(source="remaining_bags", read_only=True)
    remainingCones = serializers.IntegerField(source="remaining_cones", read_only=True)
    remaining_cones = serializers.IntegerField(read_only=True)
    remainingWeightKg = serializers.DecimalField(source="remaining_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    remainingWeightLb = serializers.DecimalField(source="remaining_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    # ── Nested outcomes (read-only, for GET detail) ───────────────────────
    outcomes = serializers.SerializerMethodField()

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
            "yarn_name", "yarn_type", "yarn_count",
            "yarnName", "yarnType", "yarnCount",
            "yarnNameId", "yarnTypeId", "yarnCountId",
            "setNo",
            "intakeDate", "supplier", "supplierDetail", "productionType",
            "stock", "stockDetail",
            "bags", "conesPerBag", "totalCones",
            "ratePerLb", "totalRate",
            "weightPerBagKg", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "returnBags", "return_bags", "returnCones", "return_cones",
            "remainingBags", "remainingCones", "remaining_cones", "remainingWeightKg", "remainingWeightLb",
            "outcomes",
            "createdBy", "updatedBy", "createdAt", "updatedAt",
        ]
        read_only_fields = [
            "id",
            "stock", "stockDetail",
            "totalCones", "totalRate", "netWeightKg", "netWeightLb",
            "outcomeBags", "outcomeWeightKg", "outcomeWeightLb",
            "returnBags", "return_bags", "returnCones", "return_cones",
            "remainingBags", "remainingCones", "remaining_cones", "remainingWeightKg", "remainingWeightLb",
            "outcomes", "supplierDetail",
            "createdAt", "updatedAt", "createdBy", "updatedBy",
        ]

    def get_outcomes(self, obj):
        outcomes = YarnOutcome.objects.filter(
            items__yarn_intake=obj
        ).distinct().order_by("-outcome_date", "-id")
        return YarnOutcomeSerializer(outcomes, many=True, context=self.context).data

    def get_stockDetail(self, obj):
        if obj.stock:
            return YarnStockMinSerializer(obj.stock).data
        return None

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

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if "set_no" in data and "setNo" not in data:
            data["setNo"] = data["set_no"]

        resolvers = [
            (["yarnNameId", "yarn_name_id", "yarnName", "yarn_name"], "yarn_name", YarnName),
            (["yarnTypeId", "yarn_type_id", "yarnType", "yarn_type"], "yarn_type", YarnType),
            (["yarnCountId", "yarn_count_id", "yarnCount", "yarn_count"], "yarn_count", YarnCount),
        ]
        for src_keys, target_field, model in resolvers:
            for k in src_keys:
                if k in data and data[k] not in (None, ""):
                    val = data[k]
                    if isinstance(val, int) or (isinstance(val, str) and val.strip().isdigit()):
                        data[target_field] = int(val)
                    elif isinstance(val, str) and val.strip():
                        obj, _ = model.objects.get_or_create(name=val.strip())
                        data[target_field] = obj.id
                    elif isinstance(val, model):
                        data[target_field] = val.id
                    break

        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret["yarnName"] = instance.yarn_name.name if instance.yarn_name else ""
        ret["yarnType"] = instance.yarn_type.name if instance.yarn_type else ""
        ret["yarnCount"] = instance.yarn_count.name if instance.yarn_count else ""
        ret["yarnNameId"] = instance.yarn_name_id
        ret["yarnTypeId"] = instance.yarn_type_id
        ret["yarnCountId"] = instance.yarn_count_id
        ret["yarnNameDetail"] = {"id": instance.yarn_name.id, "name": instance.yarn_name.name} if instance.yarn_name else None
        ret["yarnTypeDetail"] = {"id": instance.yarn_type.id, "name": instance.yarn_type.name} if instance.yarn_type else None
        ret["yarnCountDetail"] = {"id": instance.yarn_count.id, "name": instance.yarn_count.name} if instance.yarn_count else None
        ret["returnBags"] = str(instance.return_bags) if instance.return_bags is not None else "0.000000"
        ret["return_bags"] = str(instance.return_bags) if instance.return_bags is not None else "0.000000"
        ret["returnCones"] = str(instance.return_cones) if instance.return_cones is not None else "0.000000"
        ret["return_cones"] = str(instance.return_cones) if instance.return_cones is not None else "0.000000"
        ret["remainingCones"] = instance.remaining_cones
        ret["remaining_cones"] = instance.remaining_cones
        return ret

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None
        if user:
            validated_data["created_by"] = user
            validated_data["updated_by"] = user

        with transaction.atomic():
            from factory.yarn.yarn_stock.services import get_or_create_yarn_stock, recalculate_yarn_stock
            yarn_name_val = validated_data.pop("yarn_name", None)
            yarn_type_val = validated_data.pop("yarn_type", None)
            yarn_count_val = validated_data.pop("yarn_count", None)
            for k in ["yarnName", "yarnType", "yarnCount", "yarnNameId", "yarnTypeId", "yarnCountId"]:
                validated_data.pop(k, None)

            stock = get_or_create_yarn_stock(
                yarn_name=yarn_name_val,
                yarn_type=yarn_type_val,
                yarn_count=yarn_count_val,
                production_type=validated_data.get("production_type", ""),
                user=user,
            )
            validated_data["stock"] = stock
            validated_data["yarn_name"] = stock.yarn_name
            validated_data["yarn_type"] = stock.yarn_type
            validated_data["yarn_count"] = stock.yarn_count

            intake = YarnIntake(**validated_data)
            intake.calculate_intake_fields()
            intake.init_remaining_stock()
            intake.save()

            locked_stock = YarnStock.objects.select_for_update().get(pk=stock.pk)
            recalculate_yarn_stock(locked_stock)
            return intake

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None
        if user:
            validated_data["updated_by"] = user

        with transaction.atomic():
            from factory.yarn.yarn_stock.services import get_or_create_yarn_stock, recalculate_yarn_stock
            old_stock = instance.stock

            new_yarn_name = validated_data.get("yarn_name", instance.yarn_name)
            new_yarn_type = validated_data.get("yarn_type", instance.yarn_type)
            new_yarn_count = validated_data.get("yarn_count", instance.yarn_count)
            new_prod_type = validated_data.get("production_type", instance.production_type)

            new_yarn_name_id = new_yarn_name.id if hasattr(new_yarn_name, "id") else new_yarn_name
            new_yarn_type_id = new_yarn_type.id if hasattr(new_yarn_type, "id") else new_yarn_type
            new_yarn_count_id = new_yarn_count.id if hasattr(new_yarn_count, "id") else new_yarn_count

            category_changed = (
                old_stock and (
                    old_stock.yarn_name_id != new_yarn_name_id
                    or old_stock.yarn_type_id != new_yarn_type_id
                    or old_stock.yarn_count_id != new_yarn_count_id
                    or old_stock.production_type != (new_prod_type or "").strip()
                )
            )

            if category_changed:
                new_stock = get_or_create_yarn_stock(
                    yarn_name=new_yarn_name,
                    yarn_type=new_yarn_type,
                    yarn_count=new_yarn_count,
                    production_type=new_prod_type,
                    user=user,
                )
                # Verify old stock won't become negative
                locked_old = YarnStock.objects.select_for_update().get(pk=old_stock.pk)
                remaining_bags = locked_old.intakes.exclude(pk=instance.pk).aggregate(Sum("bags"))["bags__sum"] or 0
                dispatched_bags = locked_old.outcomes.aggregate(Sum("outcome_bags"))["outcome_bags__sum"] or 0
                if remaining_bags < dispatched_bags:
                    old_name = locked_old.yarn_name.name if locked_old.yarn_name else ""
                    raise serializers.ValidationError({
                        "yarnName": [
                            f"Cannot change yarn category: previous stock pool '{old_name}' "
                            f"has dispatched outcomes ({dispatched_bags} bags) exceeding remaining intakes ({remaining_bags} bags)."
                        ]
                    })
                instance.stock = new_stock

            for k in ["yarnName", "yarnType", "yarnCount", "yarnNameId", "yarnTypeId", "yarnCountId"]:
                validated_data.pop(k, None)

            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.calculate_intake_fields()
            instance.save()

            if category_changed and old_stock:
                locked_old = YarnStock.objects.select_for_update().get(pk=old_stock.pk)
                recalculate_yarn_stock(locked_old)
            if instance.stock:
                locked_curr = YarnStock.objects.select_for_update().get(pk=instance.stock.pk)
                recalculate_yarn_stock(locked_curr)

            from .services import recalculate_yarn_intake_stock
            recalculate_yarn_intake_stock(instance)
            instance.refresh_from_db()
            return instance
