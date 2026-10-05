"""
Serializers for the Beam module.
"""

from rest_framework import serializers
from .models import Beam


class BeamListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list / table views.
    """
    beamName = serializers.CharField(
        source="beam_name", required=False, allow_blank=True
    )
    beamNumber = serializers.CharField(source="beam_number")
    yarnCount = serializers.CharField(
        source="yarn_count", required=False, allow_blank=True
    )
    warpCount = serializers.IntegerField(
        source="warp_count", required=False, allow_null=True
    )
    totalEnds = serializers.IntegerField(
        source="total_ends", required=False, allow_null=True
    )
    productionOrder = serializers.CharField(
        source="production_order", required=False, allow_blank=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

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


class BeamDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create / retrieve / update operations.
    Includes notes field not shown in list view.
    """
    beamName = serializers.CharField(
        source="beam_name", required=False, allow_blank=True, default=""
    )
    beamNumber = serializers.CharField(source="beam_number")
    yarnCount = serializers.CharField(
        source="yarn_count", required=False, allow_blank=True, default=""
    )
    warpCount = serializers.IntegerField(
        source="warp_count", required=False, allow_null=True
    )
    totalEnds = serializers.IntegerField(
        source="total_ends", required=False, allow_null=True
    )
    length = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    weight = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    productionOrder = serializers.CharField(
        source="production_order", required=False, allow_blank=True, default=""
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

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

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate_beamNumber(self, value):  # noqa: N802
        beam_id = self.instance.id if self.instance else None
        if (
            Beam.objects
            .filter(beam_number__iexact=value)
            .exclude(id=beam_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A beam with this number already exists."
            )
        return value

    def validate_status(self, value):
        if value == Beam.StatusChoices.AVAILABLE and self.instance:
            from factory.yarn.sizing.models import SizingBeamAssignment
            has_active = SizingBeamAssignment.objects.filter(
                beam=self.instance,
                status__in=[
                    SizingBeamAssignment.StatusChoices.ASSIGNED,
                    SizingBeamAssignment.StatusChoices.IN_USE,
                    SizingBeamAssignment.StatusChoices.RECEIVED,
                ]
            ).exists()
            if has_active:
                raise serializers.ValidationError(
                    "Cannot set beam status directly to 'Available' while it has an active sizing assignment. "
                    "Use the release endpoint to release the beam when it is emptied."
                )
        return value


    # ------------------------------------------------------------------ #
    # Create / Update (auto-assign created_by / updated_by)
    # ------------------------------------------------------------------ #

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


# ── Loom Minimal Serializer ──────────────────────────────────────────────────

class LoomMinSerializer(serializers.ModelSerializer):
    loomCode = serializers.CharField(source="loom_code")
    loomName = serializers.CharField(source="loom_name")

    class Meta:
        from factory.loom.models import Loom
        model = Loom
        fields = ["id", "loomCode", "loomName", "status"]


# ── BeamLoading Serializers ──────────────────────────────────────────────────

class BeamLoadingSerializer(serializers.ModelSerializer):
    """
    Serializer for BeamLoading: "Loading the returned Sizing Set onto an existing Beam
    and installing that Beam onto a Loom."
    """
    from factory.yarn.sizing.models import SizingOutcome
    from factory.loom.models import Loom
    from .models import BeamLoading

    sizingOutcome = serializers.PrimaryKeyRelatedField(
        source="sizing_outcome",
        queryset=SizingOutcome.objects.all(),
        required=False,
    )
    sizingOutcomeId = serializers.IntegerField(source="sizing_outcome_id", required=False, write_only=True)

    beam = serializers.PrimaryKeyRelatedField(
        queryset=Beam.objects.all(),
        required=False,
    )
    beamId = serializers.IntegerField(source="beam_id", required=False, write_only=True)

    loom = serializers.PrimaryKeyRelatedField(
        queryset=Loom.objects.all(),
        required=False,
    )
    loomId = serializers.IntegerField(source="loom_id", required=False, write_only=True)

    # Flat convenience fields
    setNo = serializers.SerializerMethodField()
    beamNumber = serializers.SerializerMethodField()
    loomNumber = serializers.SerializerMethodField()
    loomCode = serializers.SerializerMethodField()

    # Rich nested details
    sizingOutcomeDetail = serializers.SerializerMethodField()
    beamDetail = serializers.SerializerMethodField()
    loomDetail = serializers.SerializerMethodField()

    # Spec fields
    warpCount = serializers.CharField(source="warp_count", required=False, allow_blank=True, default="")
    weftCount = serializers.CharField(source="weft_count", required=False, allow_blank=True, default="")
    reedWidth = serializers.DecimalField(source="reed_width", max_digits=10, decimal_places=2, required=False, allow_null=True)
    pick = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    reedCount = serializers.DecimalField(source="reed_count", max_digits=10, decimal_places=2, required=False, allow_null=True)
    pickCount = serializers.DecimalField(source="pick_count", max_digits=10, decimal_places=2, required=False, allow_null=True)
    shortage = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    width = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    lakhai = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    installationDate = serializers.DateField(source="installation_date", required=False, allow_null=True)

    totalMetersProduced = serializers.SerializerMethodField()

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        from .models import BeamLoading
        model = BeamLoading
        fields = [
            "id",
            "sizingOutcome",
            "sizingOutcomeId",
            "sizingOutcomeDetail",
            "beam",
            "beamId",
            "beamNumber",
            "beamDetail",
            "loom",
            "loomId",
            "loomCode",
            "loomNumber",
            "loomDetail",
            "setNo",
            "warpCount",
            "weftCount",
            "reedWidth",
            "pick",
            "reedCount",
            "pickCount",
            "shortage",
            "width",
            "lakhai",
            "installationDate",
            "status",
            "totalMetersProduced",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "status",
            "setNo",
            "beamNumber",
            "loomCode",
            "loomNumber",
            "sizingOutcomeDetail",
            "beamDetail",
            "loomDetail",
            "totalMetersProduced",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_setNo(self, obj):
        return obj.sizing_outcome.set_no if obj.sizing_outcome else ""

    def get_beamNumber(self, obj):
        return obj.beam.beam_number if obj.beam else ""

    def get_loomCode(self, obj):
        return obj.loom.loom_code if obj.loom else ""

    def get_loomNumber(self, obj):
        return obj.loom.loom_code if obj.loom else ""

    def get_sizingOutcomeDetail(self, obj):
        if obj.sizing_outcome:
            return {
                "id": obj.sizing_outcome.id,
                "setNo": obj.sizing_outcome.set_no,
                "sizingName": obj.sizing_outcome.sizing_name,
                "outcomeDate": obj.sizing_outcome.outcome_date,
            }
        return None

    def get_beamDetail(self, obj):
        if obj.beam:
            return {
                "id": obj.beam.id,
                "beamName": obj.beam.beam_name,
                "beamNumber": obj.beam.beam_number,
                "status": obj.beam.status,
            }
        return None

    def get_loomDetail(self, obj):
        if obj.loom:
            return {
                "id": obj.loom.id,
                "loomCode": obj.loom.loom_code,
                "loomName": obj.loom.loom_name,
                "status": obj.loom.status,
            }
        return None

    def get_totalMetersProduced(self, obj):
        if hasattr(obj, "productions"):
            from django.db.models import Sum
            total = obj.productions.aggregate(Sum("meters_produced"))["meters_produced__sum"]
            return str(total) if total is not None else "0.00"
        return "0.00"

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
        mapping = {
            "sizing_outcome": "sizingOutcome",
            "sizing_outcome_id": "sizingOutcomeId",
            "beam_id": "beamId",
            "loom_id": "loomId",
            "warp_count": "warpCount",
            "weft_count": "weftCount",
            "reed_width": "reedWidth",
            "reed_count": "reedCount",
            "pick_count": "pickCount",
            "installation_date": "installationDate",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):

        from factory.yarn.sizing.models import SizingOutcome
        from factory.loom.models import Loom

        # Resolve sizingOutcome
        sizing_outcome = attrs.get("sizing_outcome")
        so_id = self.initial_data.get("sizing_outcome") or self.initial_data.get("sizing_outcome_id") or self.initial_data.get("sizingOutcomeId")
        if not sizing_outcome and so_id:
            try:
                attrs["sizing_outcome"] = SizingOutcome.objects.get(id=so_id)
            except SizingOutcome.DoesNotExist:
                raise serializers.ValidationError({"sizingOutcome": [f"SizingOutcome with ID {so_id} does not exist."]})
        elif not sizing_outcome and not self.instance:
            raise serializers.ValidationError({"sizingOutcome": ["sizing_outcome (or sizingOutcomeId) is required."]})

        # Resolve beam
        beam = attrs.get("beam")
        b_id = self.initial_data.get("beam") or self.initial_data.get("beam_id") or self.initial_data.get("beamId")
        if not beam and b_id:
            try:
                attrs["beam"] = Beam.objects.get(id=b_id)
            except Beam.DoesNotExist:
                raise serializers.ValidationError({"beam": [f"Beam with ID {b_id} does not exist."]})
        elif not beam and not self.instance:
            raise serializers.ValidationError({"beam": ["beam (or beamId) is required."]})

        # Resolve loom
        loom = attrs.get("loom")
        l_id = self.initial_data.get("loom") or self.initial_data.get("loom_id") or self.initial_data.get("loomId")
        if not loom and l_id:
            try:
                attrs["loom"] = Loom.objects.get(id=l_id)
            except Loom.DoesNotExist:
                raise serializers.ValidationError({"loom": [f"Loom with ID {l_id} does not exist."]})
        elif not loom and not self.instance:
            raise serializers.ValidationError({"loom": ["loom (or loomId) is required."]})

        # Resolve installation_date
        inst_date = attrs.get("installation_date") or self.initial_data.get("installation_date") or self.initial_data.get("installationDate")
        if inst_date and not attrs.get("installation_date"):
            attrs["installation_date"] = inst_date

        return attrs

    def create(self, validated_data):
        from .services import load_beam_onto_loom
        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None

        sizing_outcome = validated_data.pop("sizing_outcome")
        beam = validated_data.pop("beam")
        loom = validated_data.pop("loom")

        return load_beam_onto_loom(
            sizing_outcome=sizing_outcome,
            beam_or_id=beam,
            loom_or_id=loom,
            user=user,
            request=request,
            **validated_data,
        )


class BatchBeamLoadingSerializer(serializers.Serializer):
    """
    Serializer to load multiple Beams for a single SizingOutcome in one API call.
    Payload:
      {
        "sizing_outcome": 25,
        "loadings": [
          { "beam_id": 101, "loom_id": 1, "installation_date": "2026-10-03" },
          { "beam_id": 102, "loom_id": 2, "installation_date": "2026-10-03" }
        ]
      }
    """
    sizing_outcome = serializers.IntegerField(required=False)
    sizingOutcomeId = serializers.IntegerField(required=False)
    loadings = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate(self, attrs):
        from factory.yarn.sizing.models import SizingOutcome
        so_id = attrs.get("sizing_outcome") or attrs.get("sizingOutcomeId") or self.initial_data.get("sizing_outcome") or self.initial_data.get("sizingOutcomeId")
        if not so_id:
            raise serializers.ValidationError({"sizing_outcome": ["sizing_outcome ID is required."]})
        try:
            attrs["sizing_outcome_obj"] = SizingOutcome.objects.get(id=so_id)
        except SizingOutcome.DoesNotExist:
            raise serializers.ValidationError({"sizing_outcome": [f"SizingOutcome #{so_id} does not exist."]})

        loadings = attrs.get("loadings", [])
        if not loadings:
            raise serializers.ValidationError({"loadings": ["At least one loading item is required."]})

        # Check for duplicate beams in payload
        beam_ids = [item.get("beam_id") or item.get("beamId") or item.get("beam") for item in loadings]
        if len(beam_ids) != len(set(beam_ids)):
            raise serializers.ValidationError({"loadings": ["Duplicate beam IDs detected in the batch loading list."]})

        # Check for duplicate looms in payload
        loom_ids = [item.get("loom_id") or item.get("loomId") or item.get("loom") for item in loadings]
        if len(loom_ids) != len(set(loom_ids)):
            raise serializers.ValidationError({"loadings": ["Duplicate loom IDs detected in the batch loading list."]})

        return attrs


# ── Production Serializer ────────────────────────────────────────────────────

class ProductionSerializer(serializers.ModelSerializer):
    """
    Records cloth/fabric production built from a loaded Beam on a Loom.
    """
    from .models import BeamLoading, Production

    beamLoading = serializers.PrimaryKeyRelatedField(
        source="beam_loading",
        queryset=BeamLoading.objects.all(),
        required=False,
    )
    beamLoadingId = serializers.IntegerField(source="beam_loading_id", required=False, write_only=True)

    beamDetail = serializers.SerializerMethodField()
    loomDetail = serializers.SerializerMethodField()

    productionDate = serializers.DateField(source="production_date", required=False)
    shift = serializers.CharField(required=False, allow_blank=True, default="General")
    metersProduced = serializers.DecimalField(source="meters_produced", max_digits=12, decimal_places=2)
    operatorName = serializers.CharField(source="operator_name", required=False, allow_blank=True, default="")
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    beamEmptied = serializers.BooleanField(source="beam_emptied", required=False, default=False)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        from .models import Production
        model = Production
        fields = [
            "id",
            "beamLoading",
            "beamLoadingId",
            "beamDetail",
            "loomDetail",
            "productionDate",
            "shift",
            "metersProduced",
            "operatorName",
            "remarks",
            "beamEmptied",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id",
            "beamDetail",
            "loomDetail",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_beamDetail(self, obj):
        if obj.beam:
            return {"id": obj.beam.id, "beamNumber": obj.beam.beam_number, "status": obj.beam.status}
        return None

    def get_loomDetail(self, obj):
        if obj.loom:
            return {"id": obj.loom.id, "loomCode": obj.loom.loom_code, "status": obj.loom.status}
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
        mapping = {
            "beam_loading": "beamLoading",
            "beam_loading_id": "beamLoadingId",
            "production_date": "productionDate",
            "meters_produced": "metersProduced",
            "operator_name": "operatorName",
            "beam_emptied": "beamEmptied",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):

        from .models import BeamLoading

        loading = attrs.get("beam_loading")
        loading_id = (
            self.initial_data.get("beam_loading")
            or self.initial_data.get("beam_loading_id")
            or self.initial_data.get("beamLoadingId")
            or self.initial_data.get("beamLoading")
        )

        if not loading and loading_id:
            try:
                attrs["beam_loading"] = BeamLoading.objects.get(id=loading_id)
            except BeamLoading.DoesNotExist:
                raise serializers.ValidationError({
                    "beamLoading": [f"BeamLoading #{loading_id} does not exist."]
                })
        elif not loading and not self.instance:
            raise serializers.ValidationError({
                "beamLoading": ["beam_loading (or beamLoadingId) is required."]
            })

        prod_date = attrs.get("production_date") or self.initial_data.get("production_date") or self.initial_data.get("productionDate")
        if not prod_date and not self.instance:
            raise serializers.ValidationError({
                "productionDate": ["productionDate (or production_date) is required."]
            })
        if prod_date and not attrs.get("production_date"):
            attrs["production_date"] = prod_date

        return attrs

    def create(self, validated_data):
        from .services import record_production_entry
        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None

        loading = validated_data.pop("beam_loading")
        production_date = validated_data.pop("production_date")
        meters_produced = validated_data.pop("meters_produced")
        shift = validated_data.pop("shift", "General")
        operator_name = validated_data.pop("operator_name", "")
        remarks = validated_data.pop("remarks", "")
        beam_emptied = validated_data.pop("beam_emptied", False)

        return record_production_entry(
            beam_loading_or_id=loading,
            production_date=production_date,
            meters_produced=meters_produced,
            shift=shift,
            operator_name=operator_name,
            remarks=remarks,
            beam_emptied=beam_emptied,
            user=user,
            request=request,
        )

