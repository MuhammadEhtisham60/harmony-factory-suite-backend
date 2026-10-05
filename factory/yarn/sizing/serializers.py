"""
Serializers for Sizing, SizingOutcome, and SizingBeamAssignment modules.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.beam.models import Beam
from factory.yarn.yarn_intake.models import YarnOutcome
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.yarn.sizing.services import create_sizing_outcome, assign_beams_to_outcome


# ── Minimal / Nested Serializers ─────────────────────────────────────────────

class YarnOutcomeMinSerializer(serializers.ModelSerializer):
    """Minimal YarnOutcome details for nested responses."""
    yarnName = serializers.CharField(source="yarn_intake.yarn_name", read_only=True)
    yarnType = serializers.CharField(source="yarn_intake.yarn_type", read_only=True)
    yarnCount = serializers.CharField(source="yarn_intake.yarn_count", read_only=True)
    intakeSetNo = serializers.CharField(source="yarn_intake.set_no", read_only=True)
    sizingName = serializers.CharField(source="sizing.sizing_name", read_only=True)

    class Meta:
        model = YarnOutcome
        fields = ["id", "outcome_type", "outcome_bags", "yarnName", "yarnType", "yarnCount", "intakeSetNo", "sizingName"]


class SizingMinSerializer(serializers.ModelSerializer):
    """Minimal Sizing details for nested responses."""
    sizingName = serializers.CharField(source="sizing_name")
    contactPerson = serializers.CharField(source="contact_person")
    phoneNo = serializers.CharField(source="phone_no")

    class Meta:
        model = Sizing
        fields = ["id", "sizingName", "contactPerson", "phoneNo", "status"]


class BeamMinSerializer(serializers.ModelSerializer):
    """Minimal Beam details for assignment responses."""
    beamName = serializers.CharField(source="beam_name")
    beamNumber = serializers.CharField(source="beam_number")
    yarnCount = serializers.CharField(source="yarn_count")
    warpCount = serializers.IntegerField(source="warp_count")
    totalEnds = serializers.IntegerField(source="total_ends")
    productionOrder = serializers.CharField(source="production_order")
    beamYarnLength = serializers.SerializerMethodField()
    beam_yarn_length = serializers.SerializerMethodField()

    class Meta:
        model = Beam
        fields = [
            "id",
            "beamName",
            "beamNumber",
            "yarnCount",
            "warpCount",
            "totalEnds",
            "length",
            "weight",
            "productionOrder",
            "status",
            "beamYarnLength",
            "beam_yarn_length",
        ]

    def get_beamYarnLength(self, obj):
        assignment = self.context.get("assignment")
        if assignment and hasattr(assignment, "get_beam_yarn_length"):
            return assignment.get_beam_yarn_length(obj.id)
        return None

    def get_beam_yarn_length(self, obj):
        return self.get_beamYarnLength(obj)


# ── Sizing Unit Serializer ───────────────────────────────────────────────────

class SizingSerializer(serializers.ModelSerializer):
    sizingName = serializers.CharField(source="sizing_name")
    contactPerson = serializers.CharField(
        source="contact_person", required=False, allow_blank=True, default=""
    )
    contactNumber = serializers.CharField(
        source="phone_no", required=False, allow_blank=True
    )
    phoneNo = serializers.CharField(
        source="phone_no", required=False, allow_blank=True
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=Sizing.StatusChoices.choices,
        required=False,
        default=Sizing.StatusChoices.ACTIVE,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = Sizing
        fields = [
            "id",
            "sizingName",
            "contactPerson",
            "contactNumber",
            "phoneNo",
            "email",
            "address",
            "status",
            "notes",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt", "createdBy", "updatedBy"]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


# ── SizingBeamAssignment Serializer ──────────────────────────────────────────

class SizingBeamAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer representing a Beam assignment to a YarnOutcome.
    Supports full CRUD operations, nested beam details, and beam_yarn_length validation.
    """
    yarn_outcome = serializers.PrimaryKeyRelatedField(
        queryset=YarnOutcome.objects.all(),
        required=False,
    )
    yarnOutcome = serializers.PrimaryKeyRelatedField(
        queryset=YarnOutcome.objects.all(),
        source="yarn_outcome",
        required=False,
        write_only=True,
    )
    yarnOutcomeId = serializers.IntegerField(source="yarn_outcome_id", read_only=True)
    yarn_outcome_id = serializers.IntegerField(required=False, write_only=True)
    sizingOutcomeId = serializers.IntegerField(source="yarn_outcome_id", read_only=True)
    yarnOutcomeDetail = YarnOutcomeMinSerializer(source="yarn_outcome", read_only=True)

    beam = serializers.PrimaryKeyRelatedField(
        queryset=Beam.objects.all(),
        many=True,
        required=False,
    )
    beam_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )
    beamIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )
    beamId = serializers.SerializerMethodField()
    beam_yarn_length = serializers.DictField(
        required=False,
        default=dict,
    )
    beamYarnLength = serializers.DictField(
        required=False,
        write_only=True,
    )

    beams = serializers.SerializerMethodField()
    totalBeams = serializers.SerializerMethodField()
    status = serializers.ChoiceField(
        choices=SizingBeamAssignment.StatusChoices.choices,
        default=SizingBeamAssignment.StatusChoices.ASSIGNED,
        required=False,
    )
    assignedAt = serializers.DateTimeField(source="assigned_at", read_only=True)
    releasedAt = serializers.DateTimeField(source="released_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = SizingBeamAssignment
        fields = [
            "id",
            "yarn_outcome",
            "yarnOutcome",
            "yarnOutcomeId",
            "yarn_outcome_id",
            "sizingOutcomeId",
            "yarnOutcomeDetail",
            "beam",
            "beam_ids",
            "beamIds",
            "beamId",
            "beam_yarn_length",
            "beamYarnLength",
            "beams",
            "totalBeams",
            "status",
            "assignedAt",
            "releasedAt",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "yarnOutcomeId",
            "sizingOutcomeId",
            "yarnOutcomeDetail",
            "beamId",
            "beams",
            "totalBeams",
            "assignedAt",
            "releasedAt",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_beamId(self, obj):
        first_b = obj.beam.first()
        return first_b.id if first_b else None

    def get_beams(self, obj):
        return BeamMinSerializer(
            obj.beam.all(),
            many=True,
            context={**self.context, "assignment": obj},
        ).data

    def get_totalBeams(self, obj):
        return obj.beam.count()

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None

    def validate(self, attrs):
        # 1. Resolve yarn_outcome
        yarn_outcome = attrs.get("yarn_outcome")
        raw_yo_id = (
            self.initial_data.get("yarn_outcome_id")
            or self.initial_data.get("yarnOutcomeId")
            or self.initial_data.get("yarn_outcome")
            or self.initial_data.get("yarnOutcome")
        )
        if not yarn_outcome and raw_yo_id:
            try:
                yarn_outcome = YarnOutcome.objects.get(id=raw_yo_id)
                attrs["yarn_outcome"] = yarn_outcome
            except (YarnOutcome.DoesNotExist, ValueError):
                raise serializers.ValidationError({
                    "yarn_outcome": [f"Yarn outcome with ID {raw_yo_id} does not exist."]
                })

        if not attrs.get("yarn_outcome") and not self.instance:
            raise serializers.ValidationError({
                "yarn_outcome": ["Yarn outcome is required."]
            })

        # 2. Resolve beam list
        raw_beams = (
            attrs.get("beam")
            or attrs.get("beam_ids")
            or attrs.get("beamIds")
            or self.initial_data.get("beam")
            or self.initial_data.get("beam_ids")
            or self.initial_data.get("beamIds")
            or self.initial_data.get("beams")
        )

        final_beam_ids = None
        if raw_beams is not None:
            if isinstance(raw_beams, (int, str)) and str(raw_beams).isdigit():
                final_beam_ids = [int(raw_beams)]
            elif isinstance(raw_beams, list):
                try:
                    final_beam_ids = [int(x.id if hasattr(x, "id") else x) for x in raw_beams]
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        "beam": ["beam must be a list of integer Beam IDs."]
                    })
            else:
                raise serializers.ValidationError({
                    "beam": ["beam must be a list of valid Beam IDs."]
                })
        elif not self.instance:
            raise serializers.ValidationError({
                "beam": ["At least one beam must be selected."]
            })
        else:
            final_beam_ids = list(self.instance.beam.values_list("id", flat=True))

        # Check for duplicates
        seen = set()
        for bid in final_beam_ids:
            if bid in seen:
                raise serializers.ValidationError({
                    "beam": [f"Duplicate beam ID {bid} provided."]
                })
            seen.add(bid)

        # Verify all selected beams exist in DB
        found_beams = list(Beam.objects.filter(id__in=final_beam_ids))
        found_ids = {b.id for b in found_beams}
        missing_ids = set(final_beam_ids) - found_ids
        if missing_ids:
            raise serializers.ValidationError({
                "beam": [f"Beam with ID {mid} does not exist." for mid in sorted(list(missing_ids))]
            })

        # 3. Resolve & validate beam_yarn_length
        raw_lengths = (
            attrs.get("beam_yarn_length")
            if "beam_yarn_length" in attrs
            else (
                attrs.get("beamYarnLength")
                if "beamYarnLength" in attrs
                else (
                    self.initial_data.get("beam_yarn_length")
                    if "beam_yarn_length" in self.initial_data
                    else self.initial_data.get("beamYarnLength")
                )
            )
        )

        clean_lengths = {}
        if raw_lengths is not None:
            if not isinstance(raw_lengths, dict):
                raise serializers.ValidationError({
                    "beam_yarn_length": ["beam_yarn_length must be a dictionary/object."]
                })

            # Check extra keys in beam_yarn_length not in selected beams
            extra_keys = []
            for k in raw_lengths.keys():
                k_int = int(k) if str(k).isdigit() else None
                if k_int not in final_beam_ids and k not in final_beam_ids:
                    extra_keys.append(str(k))

            if extra_keys:
                raise serializers.ValidationError({
                    "beam_yarn_length": [
                        f"Beam ID {k} in beam_yarn_length is not selected." for k in extra_keys
                    ]
                })

            # If lengths are provided (or if non-empty), ensure every selected beam has a length
            if len(raw_lengths) > 0 or (len(final_beam_ids) > 0 and raw_lengths != {}):
                missing_lengths = []
                for bid in final_beam_ids:
                    if str(bid) not in raw_lengths and bid not in raw_lengths:
                        missing_lengths.append(bid)
                if missing_lengths:
                    raise serializers.ValidationError({
                        "beam_yarn_length": [
                            f"Missing yarn length for Beam ID {bid}." for bid in missing_lengths
                        ]
                    })

            # Validate each length value
            for k, val in raw_lengths.items():
                try:
                    num_val = float(val)
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        "beam_yarn_length": [f"Yarn length for Beam {k} must be numeric."]
                    })
                if num_val < 0:
                    raise serializers.ValidationError({
                        "beam_yarn_length": [f"Yarn length for Beam {k} cannot be negative."]
                    })

                clean_lengths[str(k)] = int(num_val) if num_val.is_integer() else num_val

            attrs["beam_yarn_length"] = clean_lengths
        elif self.instance:
            # On update without new lengths: filter existing lengths to only currently selected beams
            existing_lengths = self.instance.beam_yarn_length or {}
            clean_lengths = {
                str(k): v for k, v in existing_lengths.items()
                if (int(k) if str(k).isdigit() else k) in final_beam_ids
            }
            attrs["beam_yarn_length"] = clean_lengths

        # 4. Check active beam assignments
        target_status = attrs.get(
            "status",
            self.instance.status if self.instance else SizingBeamAssignment.StatusChoices.ASSIGNED
        )
        if target_status in [
            SizingBeamAssignment.StatusChoices.ASSIGNED,
            SizingBeamAssignment.StatusChoices.IN_USE,
        ]:
            for bid in final_beam_ids:
                active_qs = SizingBeamAssignment.objects.filter(
                    beam__id=bid,
                    status__in=[
                        SizingBeamAssignment.StatusChoices.ASSIGNED,
                        SizingBeamAssignment.StatusChoices.IN_USE,
                    ],
                )
                if self.instance:
                    active_qs = active_qs.exclude(id=self.instance.id)
                if active_qs.exists():
                    active_inst = active_qs.first()
                    raise serializers.ValidationError({
                        "beam": [
                            f"Beam {bid} is already in an active assignment (Assignment #{active_inst.id})."
                        ]
                    })

        attrs["_resolved_beams"] = found_beams
        attrs["_resolved_beam_ids"] = final_beam_ids
        return attrs

    def create(self, validated_data):
        beams = validated_data.pop("_resolved_beams", [])
        validated_data.pop("_resolved_beam_ids", None)
        validated_data.pop("beam", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beamYarnLength", None)
        validated_data.pop("yarn_outcome_id", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        assignment = SizingBeamAssignment.objects.create(**validated_data)
        if beams:
            assignment.beam.set(beams)
            for b in beams:
                if assignment.status in [SizingBeamAssignment.StatusChoices.RECEIVED, SizingBeamAssignment.StatusChoices.IN_USE]:
                    b.status = Beam.StatusChoices.LOADED
                elif b.status == Beam.StatusChoices.AVAILABLE:
                    b.status = Beam.StatusChoices.SIZING
                b.save(update_fields=["status", "updated_at"])
        return assignment

    def update(self, instance, validated_data):
        beams = validated_data.pop("_resolved_beams", None)
        validated_data.pop("_resolved_beam_ids", None)
        validated_data.pop("beam", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beamYarnLength", None)
        validated_data.pop("yarn_outcome_id", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if beams is not None:
            instance.beam.set(beams)

        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Format beam list of IDs
        beam_ids = list(instance.beam.values_list("id", flat=True)) if instance.id else []
        ret["yarn_outcome"] = instance.yarn_outcome_id
        ret["yarnOutcome"] = instance.yarn_outcome_id
        ret["yarnOutcomeId"] = instance.yarn_outcome_id
        ret["beam"] = beam_ids
        ret["beam_ids"] = beam_ids
        ret["beamIds"] = beam_ids
        ret["beam_yarn_length"] = instance.beam_yarn_length or {}
        ret["beamYarnLength"] = instance.beam_yarn_length or {}
        return ret


# ── SizingOutcome Serializer ─────────────────────────────────────────────────

class SizingOutcomeSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, retrieving, and listing SizingOutcomes.
    Supports assigning multiple existing beams during creation via `beam_ids` or `beamIds`.
    Accepts both camelCase and snake_case request parameters.
    """
    yarn_outcome = serializers.PrimaryKeyRelatedField(
        queryset=YarnOutcome.objects.all(),
        required=False,
    )
    yarnOutcome = serializers.PrimaryKeyRelatedField(
        queryset=YarnOutcome.objects.all(),
        source="yarn_outcome",
        required=False,
        write_only=True,
    )
    yarnOutcomeId = serializers.IntegerField(source="yarn_outcome_id", read_only=True)
    yarn_outcome_id = serializers.IntegerField(required=False, write_only=True)
    yarnOutcomeDetail = YarnOutcomeMinSerializer(source="yarn_outcome", read_only=True)

    # Backward compatibility for legacy sizing / sizingId callers
    sizing = serializers.PrimaryKeyRelatedField(
        queryset=Sizing.objects.all(),
        required=False,
        write_only=True,
    )
    sizingId = serializers.IntegerField(source="sizing_id", required=False, write_only=True)
    sizing_id = serializers.IntegerField(required=False, write_only=True)
    sizingDetail = SizingMinSerializer(source="sizing", read_only=True)

    setNo = serializers.CharField(source="set_no", required=False, allow_blank=True, default="")
    set_no = serializers.CharField(required=False, allow_blank=True, default="")
    setBill = serializers.CharField(source="set_bill", required=False, allow_blank=True, default="")
    set_bill = serializers.CharField(required=False, allow_blank=True, default="")
    sizingName = serializers.CharField(source="sizing_name", required=False, allow_blank=True, default="")
    sizing_name = serializers.CharField(required=False, allow_blank=True, default="")
    totalBagsOnSizing = serializers.IntegerField(source="total_bags_on_sizing", required=False, default=0)
    bagPackingCone = serializers.IntegerField(source="bag_packing_cone", required=False, default=0)
    totalCones = serializers.IntegerField(source="total_cones", required=False, default=0)
    remainingBagsOnSizingStock = serializers.IntegerField(source="remaining_bags_on_sizing_stock", required=False, default=0)
    remainingConesOnSizingStock = serializers.IntegerField(source="remaining_cones_on_sizing_stock", required=False, default=0)
    lagatBags = serializers.DecimalField(source="lagat_bags", max_digits=12, decimal_places=2, required=False, default=Decimal("0.00"))
    lagatCones = serializers.DecimalField(source="lagat_cones", max_digits=12, decimal_places=2, required=False, default=Decimal("0.00"))
    brand = serializers.CharField(required=False, allow_blank=True, default="")
    width = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    setLengthMeter = serializers.DecimalField(source="set_length_meter", max_digits=12, decimal_places=2, required=False, allow_null=True)
    setLengthGaz = serializers.DecimalField(source="set_length_gaz", max_digits=12, decimal_places=2, required=False, allow_null=True)
    totalTarr = serializers.IntegerField(source="total_tarr", required=False, allow_null=True)
    yarnBeam = serializers.CharField(source="yarn_beam", required=False, allow_blank=True, default="")
    backBeam = serializers.CharField(source="back_beam", required=False, allow_blank=True, default="")
    count = serializers.CharField(required=False, allow_blank=True, default="")
    totalSetLumbai = serializers.DecimalField(source="total_set_lumbai", max_digits=12, decimal_places=2, required=False, allow_null=True)
    totalSetShortage = serializers.DecimalField(source="total_set_shortage", max_digits=12, decimal_places=2, required=False, allow_null=True)
    ratePerKg = serializers.DecimalField(source="rate_per_kg", max_digits=12, decimal_places=2, required=False, allow_null=True)
    rate_per_kg = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    netWeightKg = serializers.DecimalField(source="net_weight_kg", max_digits=12, decimal_places=2, required=False, allow_null=True)
    net_weight_kg = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    totalRate = serializers.DecimalField(source="total_rate", max_digits=15, decimal_places=2, required=False, allow_null=True)
    total_rate = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)

    outcomeDate = serializers.DateField(source="outcome_date", required=False)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    # Write-only list of existing beam IDs to assign upon creation
    beam_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )
    beamIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )
    beam_yarn_length = serializers.DictField(
        required=False,
        write_only=True,
    )
    beamYarnLength = serializers.DictField(
        required=False,
        write_only=True,
    )

    # Read-only nested beam assignments
    beamAssignments = serializers.SerializerMethodField()
    totalBeams = serializers.IntegerField(source="total_beams", read_only=True)

    def get_beamAssignments(self, obj):
        if hasattr(obj, "beam_assignments"):
            return SizingBeamAssignmentSerializer(obj.beam_assignments.all(), many=True, context=self.context).data
        if obj.yarn_outcome_id:
            from factory.yarn.sizing.models import SizingBeamAssignment
            assignments = SizingBeamAssignment.objects.filter(yarn_outcome_id=obj.yarn_outcome_id).order_by("-assigned_at")
            return SizingBeamAssignmentSerializer(assignments, many=True, context=self.context).data
        elif obj.sizing_id:
            from factory.yarn.sizing.models import SizingBeamAssignment
            assignments = SizingBeamAssignment.objects.filter(yarn_outcome__sizing_id=obj.sizing_id).order_by("-assigned_at")
            return SizingBeamAssignmentSerializer(assignments, many=True, context=self.context).data
        return []

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = SizingOutcome
        fields = [
            "id",
            "yarn_outcome",
            "yarnOutcome",
            "yarnOutcomeId",
            "yarn_outcome_id",
            "yarnOutcomeDetail",
            "sizing",
            "sizingId",
            "sizing_id",
            "sizingDetail",
            "setNo",
            "set_no",
            "setBill",
            "set_bill",
            "sizingName",
            "sizing_name",
            "totalBagsOnSizing",
            "bagPackingCone",
            "totalCones",
            "remainingBagsOnSizingStock",
            "remainingConesOnSizingStock",
            "lagatBags",
            "lagatCones",
            "brand",
            "width",
            "setLengthMeter",
            "setLengthGaz",
            "totalTarr",
            "yarnBeam",
            "backBeam",
            "count",
            "totalSetLumbai",
            "totalSetShortage",
            "ratePerKg",
            "rate_per_kg",
            "netWeightKg",
            "net_weight_kg",
            "totalRate",
            "total_rate",
            "outcomeDate",
            "remarks",
            "beam_ids",
            "beamIds",
            "beam_yarn_length",
            "beamYarnLength",
            "beamAssignments",
            "totalBeams",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "yarnOutcomeDetail",
            "sizingDetail",
            "beamAssignments",
            "totalBeams",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "set_no": "setNo",
            "set_bill": "setBill",
            "sizing_name": "sizingName",
            "total_bags_on_sizing": "totalBagsOnSizing",
            "bag_packing_cone": "bagPackingCone",
            "total_cones": "totalCones",
            "remaining_bags_on_sizing_stock": "remainingBagsOnSizingStock",
            "remaining_cones_on_sizing_stock": "remainingConesOnSizingStock",
            "lagat_bags": "lagatBags",
            "lagat_cones": "lagatCones",
            "set_length_meter": "setLengthMeter",
            "set_length_gaz": "setLengthGaz",
            "total_tarr": "totalTarr",
            "yarn_beam": "yarnBeam",
            "back_beam": "backBeam",
            "total_set_lumbai": "totalSetLumbai",
            "total_set_shortage": "totalSetShortage",
            "rate_per_kg": "ratePerKg",
            "net_weight_kg": "netWeightKg",
            "total_rate": "totalRate",
            "outcome_date": "outcomeDate",
            "sizing_id": "sizingId",
            "yarn_outcome_id": "yarnOutcomeId",
            "beam_yarn_length": "beamYarnLength",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Resolve yarn_outcome reference from yarn_outcome / yarnOutcome / yarn_outcome_id / yarnOutcomeId
        yarn_outcome = attrs.get("yarn_outcome")
        raw_yo_id = (
            self.initial_data.get("yarn_outcome_id")
            or self.initial_data.get("yarnOutcomeId")
            or self.initial_data.get("yarn_outcome")
            or self.initial_data.get("yarnOutcome")
        )

        if not yarn_outcome and raw_yo_id:
            try:
                yarn_outcome = YarnOutcome.objects.get(id=raw_yo_id)
                attrs["yarn_outcome"] = yarn_outcome
            except (YarnOutcome.DoesNotExist, ValueError):
                raise serializers.ValidationError({
                    "yarnOutcomeId": [f"Yarn outcome with ID {raw_yo_id} does not exist."]
                })

        # Backward compatibility: resolve via sizing if yarn_outcome is not directly passed
        if not yarn_outcome:
            raw_sizing_id = (
                self.initial_data.get("sizing_id")
                or self.initial_data.get("sizingId")
                or (attrs.get("sizing").id if attrs.get("sizing") else None)
            )
            if raw_sizing_id:
                try:
                    sizing_inst = Sizing.objects.get(id=raw_sizing_id)
                    yo = None
                    raw_beam_ids = (
                        attrs.get("beam_ids")
                        or attrs.get("beamIds")
                        or self.initial_data.get("beam_ids")
                        or self.initial_data.get("beamIds")
                    )
                    if raw_beam_ids and isinstance(raw_beam_ids, list):
                        yo = YarnOutcome.objects.filter(
                            sizing=sizing_inst,
                            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                            beam_assignments__beam__id__in=raw_beam_ids,
                        ).order_by("-id").first()
                    if not yo:
                        yo = YarnOutcome.objects.filter(
                            sizing=sizing_inst,
                            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                        ).order_by("-id").first()
                    if not yo:
                        from factory.yarn.yarn_intake.models import YarnIntake, Supplier
                        from django.utils import timezone
                        intake = YarnIntake.objects.first()
                        if not intake:
                            supplier = Supplier.objects.first()
                            if not supplier:
                                supplier = Supplier.objects.create(supplier_name="Auto Supplier", status="Active")
                            intake = YarnIntake.objects.create(
                                yarn_name="Default Intake",
                                supplier=supplier,
                                bags=0,
                                cones_per_bag=0,
                                weight_per_bag_kg=0,
                                rate_per_bag=0,
                                intake_date=attrs.get("outcome_date") or timezone.now().date(),
                            )
                        yo = YarnOutcome.objects.create(
                            yarn_intake=intake,
                            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                            sizing=sizing_inst,
                            outcome_bags=0,
                            outcome_weight_per_bag_kg=0,
                            outcome_date=attrs.get("outcome_date") or timezone.now().date(),
                        )
                    if yo:
                        attrs["yarn_outcome"] = yo
                except Sizing.DoesNotExist:
                    raise serializers.ValidationError({
                        "sizingId": [f"Sizing unit with ID {raw_sizing_id} does not exist."]
                    })

        if not attrs.get("yarn_outcome") and not self.instance:
            raise serializers.ValidationError({
                "yarn_outcome": ["Yarn outcome reference (yarn_outcome or yarn_outcome_id) is required."]
            })

        # Resolve outcome_date
        outcome_date = attrs.get("outcome_date") or self.initial_data.get("outcome_date") or self.initial_data.get("outcomeDate")
        if not outcome_date and not self.instance:
            raise serializers.ValidationError({
                "outcomeDate": ["outcomeDate (or outcome_date) is required."]
            })
        if outcome_date and not attrs.get("outcome_date"):
            attrs["outcome_date"] = outcome_date

        # Resolve beam IDs
        raw_beam_ids = (
            attrs.get("beam_ids")
            or attrs.get("beamIds")
            or self.initial_data.get("beam_ids")
            or self.initial_data.get("beamIds")
        )
        if raw_beam_ids is not None:
            if not isinstance(raw_beam_ids, list):
                raise serializers.ValidationError({
                    "beam_ids": ["beam_ids must be a list of integer IDs."]
                })
            attrs["_resolved_beam_ids"] = raw_beam_ids

        # Resolve beam_yarn_length
        raw_lengths = (
            attrs.get("beam_yarn_length")
            or attrs.get("beamYarnLength")
            or self.initial_data.get("beam_yarn_length")
            or self.initial_data.get("beamYarnLength")
        )
        if raw_lengths is not None:
            if not isinstance(raw_lengths, dict):
                raise serializers.ValidationError({
                    "beam_yarn_length": ["beam_yarn_length must be a dictionary."]
                })
            attrs["_resolved_beam_yarn_length"] = raw_lengths

        return attrs

    def create(self, validated_data):
        resolved_beam_ids = validated_data.pop("_resolved_beam_ids", None)
        resolved_beam_yarn_length = validated_data.pop("_resolved_beam_yarn_length", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beam_yarn_length", None)
        validated_data.pop("beamYarnLength", None)
        validated_data.pop("sizing_id", None)
        validated_data.pop("sizing", None)
        validated_data.pop("yarn_outcome_id", None)

        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None

        yarn_outcome = validated_data.pop("yarn_outcome")
        outcome_date = validated_data.pop("outcome_date")
        remarks = validated_data.pop("remarks", "")

        return create_sizing_outcome(
            yarn_outcome=yarn_outcome,
            outcome_date=outcome_date,
            remarks=remarks,
            beam_ids=resolved_beam_ids,
            beam_yarn_length=resolved_beam_yarn_length,
            user=user,
            request=request,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("_resolved_beam_ids", None)
        validated_data.pop("_resolved_beam_yarn_length", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("beam_yarn_length", None)
        validated_data.pop("beamYarnLength", None)
        validated_data.pop("sizing_id", None)
        validated_data.pop("sizing", None)
        validated_data.pop("yarn_outcome_id", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


# ── Action Request Serializers ───────────────────────────────────────────────

class AssignBeamsSerializer(serializers.Serializer):
    """
    Payload for assigning additional existing Beams to an existing SizingOutcome.
    Accepts:
      { "beam_ids": [101, 102], "beam_yarn_length": { "101": 5000, "102": 4500 } }
    """
    beam_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    beamIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    beam_yarn_length = serializers.DictField(
        required=False,
    )
    beamYarnLength = serializers.DictField(
        required=False,
    )

    def validate(self, attrs):
        ids = (
            attrs.get("beam_ids")
            or attrs.get("beamIds")
            or self.initial_data.get("beam_ids")
            or self.initial_data.get("beamIds")
        )
        if not ids or not isinstance(ids, list):
            raise serializers.ValidationError({
                "beam_ids": ["A non-empty list of beam IDs (beam_ids or beamIds) is required."]
            })
        attrs["beam_ids"] = ids

        lengths = (
            attrs.get("beam_yarn_length")
            or attrs.get("beamYarnLength")
            or self.initial_data.get("beam_yarn_length")
            or self.initial_data.get("beamYarnLength")
        )
        if lengths is not None and isinstance(lengths, dict):
            attrs["beam_yarn_length"] = lengths

        return attrs


class ReleaseBeamRequestSerializer(serializers.Serializer):
    """
    Payload for releasing a Beam from a SizingOutcome or Beam endpoint.
    Accepts beam_id, beamId, or assignment_id.
    """
    beam_id = serializers.IntegerField(required=False)
    beamId = serializers.IntegerField(required=False)
    assignment_id = serializers.IntegerField(required=False)
    assignmentId = serializers.IntegerField(required=False)

    def validate(self, attrs):
        bid = attrs.get("beam_id") or attrs.get("beamId") or self.initial_data.get("beam_id") or self.initial_data.get("beamId")
        aid = attrs.get("assignment_id") or attrs.get("assignmentId") or self.initial_data.get("assignment_id") or self.initial_data.get("assignmentId")

        if not bid and not aid:
            raise serializers.ValidationError(
                "Either beam_id (beamId) or assignment_id (assignmentId) must be provided."
            )
        attrs["resolved_beam_id"] = bid
        attrs["resolved_assignment_id"] = aid
        return attrs


class TransitionAssignmentSerializer(serializers.Serializer):
    """
    Payload for transitioning a SizingBeamAssignment status.
    Accepts:
      { "status": "IN_USE" | "COMPLETED" | "RELEASED" }
    """
    status = serializers.ChoiceField(choices=SizingBeamAssignment.StatusChoices.choices)


# ── Beam Sizing History Serializer ───────────────────────────────────────────

class BeamAssignmentHistorySerializer(serializers.ModelSerializer):
    """
    Rich serializer representing one historical sizing cycle of a Beam,
    including the YarnOutcome, Sizing Unit details, and related dispatched yarn.
    """
    assignmentId = serializers.IntegerField(source="id", read_only=True)
    yarnOutcome = serializers.SerializerMethodField()
    sizingOutcome = serializers.SerializerMethodField()
    beamYarnLength = serializers.SerializerMethodField()
    assignedAt = serializers.DateTimeField(source="assigned_at", read_only=True)
    releasedAt = serializers.DateTimeField(source="released_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = SizingBeamAssignment
        fields = [
            "assignmentId",
            "status",
            "assignedAt",
            "releasedAt",
            "beamYarnLength",
            "yarnOutcome",
            "sizingOutcome",
            "createdBy",
            "updatedBy",
        ]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def get_beamYarnLength(self, obj):
        beam_id = self.context.get("beam_id")
        if beam_id and hasattr(obj, "get_beam_yarn_length"):
            return obj.get_beam_yarn_length(beam_id)
        return obj.beam_yarn_length

    def get_yarnOutcome(self, obj):
        yo = getattr(obj, "yarn_outcome", None)
        if not yo:
            return None

        sizing = getattr(yo, "sizing", None)
        intake = getattr(yo, "yarn_intake", None)

        return {
            "id": yo.id,
            "outcomeType": yo.outcome_type,
            "outcomeBags": yo.outcome_bags,
            "outcomeWeightKg": str(yo.outcome_weight_kg),
            "outcomeDate": yo.outcome_date,
            "yarnName": intake.yarn_name if intake else None,
            "yarnCount": intake.yarn_count if intake else None,
            "sizing": {
                "id": sizing.id if sizing else None,
                "sizingName": sizing.sizing_name if sizing else None,
                "contactPerson": sizing.contact_person if sizing else None,
                "phoneNo": sizing.phone_no if sizing else None,
            } if sizing else None,
        }

    def get_sizingOutcome(self, obj):
        return self.get_yarnOutcome(obj)
