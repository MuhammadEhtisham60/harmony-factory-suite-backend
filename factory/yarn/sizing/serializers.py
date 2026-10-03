"""
Serializers for Sizing, SizingOutcome, and SizingBeamAssignment modules.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.beam.models import Beam
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.yarn.sizing.services import create_sizing_outcome, assign_beams_to_outcome


# ── Minimal / Nested Serializers ─────────────────────────────────────────────

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
        ]


# ── Sizing Unit Serializer ───────────────────────────────────────────────────

class SizingSerializer(serializers.ModelSerializer):
    sizingName = serializers.CharField(source="sizing_name")
    contactPerson = serializers.CharField(
        source="contact_person", required=False, allow_blank=True, default=""
    )
    phoneNo = serializers.CharField(
        source="phone_no", required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(required=False, default="Active")
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
    Serializer representing a Beam assignment to a SizingOutcome.
    Includes rich nested beam information.
    """
    sizingOutcomeId = serializers.IntegerField(source="sizing_outcome_id", read_only=True)
    beamId = serializers.IntegerField(source="beam_id", read_only=True)
    beam = BeamMinSerializer(read_only=True)
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
            "sizingOutcomeId",
            "beamId",
            "beam",
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
            "sizingOutcomeId",
            "beamId",
            "beam",
            "status",
            "assignedAt",
            "releasedAt",
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


# ── SizingOutcome Serializer ─────────────────────────────────────────────────

class SizingOutcomeSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, retrieving, and listing SizingOutcomes.
    Supports assigning multiple existing beams during creation via `beam_ids` or `beamIds`.
    Accepts both camelCase and snake_case request parameters.
    """
    sizing = serializers.PrimaryKeyRelatedField(
        queryset=Sizing.objects.all(),
        required=False,
    )
    sizingId = serializers.IntegerField(source="sizing_id", required=False, write_only=True)
    sizingDetail = SizingMinSerializer(source="sizing", read_only=True)

    setNo = serializers.CharField(source="set_no", required=False, allow_blank=True, default="")
    sizingName = serializers.CharField(source="sizing_name", required=False, allow_blank=True, default="")
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

    # Read-only nested beam assignments
    beamAssignments = SizingBeamAssignmentSerializer(
        source="beam_assignments",
        many=True,
        read_only=True,
    )
    totalBeams = serializers.IntegerField(source="total_beams", read_only=True)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = SizingOutcome
        fields = [
            "id",
            "sizing",
            "sizingId",
            "sizingDetail",
            "setNo",
            "sizingName",
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
            "outcomeDate",
            "remarks",
            "beam_ids",
            "beamIds",
            "beamAssignments",
            "totalBeams",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
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
    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "set_no": "setNo",
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
            "outcome_date": "outcomeDate",
            "sizing_id": "sizingId",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):

        # Resolve sizing reference from either `sizing`, `sizing_id`, or `sizingId`
        sizing = attrs.get("sizing")
        raw_sizing_id = self.initial_data.get("sizing_id") or self.initial_data.get("sizingId")

        if not sizing and raw_sizing_id:
            try:
                sizing = Sizing.objects.get(id=raw_sizing_id)
                attrs["sizing"] = sizing
            except Sizing.DoesNotExist:
                raise serializers.ValidationError({
                    "sizingId": [f"Sizing unit with ID {raw_sizing_id} does not exist."]
                })

        if not sizing and not self.instance:
            raise serializers.ValidationError({
                "sizing": ["Sizing reference (sizing or sizing_id) is required."]
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

        return attrs

    def create(self, validated_data):
        resolved_beam_ids = validated_data.pop("_resolved_beam_ids", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("sizing_id", None)

        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None

        sizing = validated_data.pop("sizing")
        outcome_date = validated_data.pop("outcome_date")
        remarks = validated_data.pop("remarks", "")

        return create_sizing_outcome(
            sizing=sizing,
            outcome_date=outcome_date,
            remarks=remarks,
            beam_ids=resolved_beam_ids,
            user=user,
            request=request,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("_resolved_beam_ids", None)
        validated_data.pop("beam_ids", None)
        validated_data.pop("beamIds", None)
        validated_data.pop("sizing_id", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)



# ── Action Request Serializers ───────────────────────────────────────────────

class AssignBeamsSerializer(serializers.Serializer):
    """
    Payload for assigning additional existing Beams to an existing SizingOutcome.
    Accepts:
      { "beam_ids": [101, 102] } or { "beamIds": [101, 102] }
    """
    beam_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    beamIds = serializers.ListField(
        child=serializers.IntegerField(),
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
    including the SizingOutcome, Sizing Unit details, and related dispatched yarn.
    """
    assignmentId = serializers.IntegerField(source="id", read_only=True)
    sizingOutcome = serializers.SerializerMethodField()
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

    def get_sizingOutcome(self, obj):
        so = obj.sizing_outcome
        if not so:
            return None

        # Related dispatched yarn to this sizing unit
        sizing = so.sizing
        dispatched_yarns = []
        if sizing and hasattr(sizing, "yarn_outcomes"):
            for yo in sizing.yarn_outcomes.all():
                dispatched_yarns.append({
                    "id": yo.id,
                    "yarnName": yo.yarn_intake.yarn_name if yo.yarn_intake else None,
                    "yarnCount": yo.yarn_intake.yarn_count if yo.yarn_intake else None,
                    "outcomeBags": yo.outcome_bags,
                    "outcomeWeightKg": str(yo.outcome_weight_kg),
                    "outcomeDate": yo.outcome_date,
                })

        return {
            "id": so.id,
            "outcomeDate": so.outcome_date,
            "remarks": so.remarks,
            "sizing": {
                "id": sizing.id if sizing else None,
                "sizingName": sizing.sizing_name if sizing else None,
                "contactPerson": sizing.contact_person if sizing else None,
                "phoneNo": sizing.phone_no if sizing else None,
            } if sizing else None,
            "dispatchedYarns": dispatched_yarns,
        }
