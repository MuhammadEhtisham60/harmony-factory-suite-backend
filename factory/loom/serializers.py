"""
Serializers for the Loom module.
"""

from rest_framework import serializers
from .models import Loom


class LoomListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list / table views.
    """
    loomCode = serializers.CharField(source="loom_code")
    loomName = serializers.CharField(source="loom_name")
    modelNumber = serializers.CharField(
        source="model_number", required=False, allow_blank=True
    )
    installationDate = serializers.DateField(
        source="installation_date", required=False, allow_null=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = Loom
        fields = [
            "id",
            "loomCode",
            "loomName",
            "modelNumber",
            "width",
            "installationDate",
            "location",
            "status",
            "currentBeamId",
            "currentBeamNo",
            "currentLoadingId",
            "currentSetNo",
            "clothQuality",
            "clothName",
            "beamLength",
            "producedMeters",
            "remainingMeters",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    currentBeamId = serializers.SerializerMethodField()
    currentBeamNo = serializers.SerializerMethodField()
    currentLoadingId = serializers.SerializerMethodField()
    currentSetNo = serializers.SerializerMethodField()
    clothQuality = serializers.SerializerMethodField()
    clothName = serializers.SerializerMethodField()
    beamLength = serializers.SerializerMethodField()
    producedMeters = serializers.SerializerMethodField()
    remainingMeters = serializers.SerializerMethodField()

    def _get_active_loading(self, obj):
        if not hasattr(obj, "_cached_active_loading"):
            obj._cached_active_loading = obj.beam_loadings.filter(
                status__in=["Loaded", "In Production"]
            ).first()
        return obj._cached_active_loading

    def get_currentBeamId(self, obj):
        loading = self._get_active_loading(obj)
        return loading.beam.id if loading and loading.beam else None

    def get_currentBeamNo(self, obj):
        loading = self._get_active_loading(obj)
        return loading.beam.beam_number if loading and loading.beam else None

    def get_currentLoadingId(self, obj):
        loading = self._get_active_loading(obj)
        return loading.id if loading else None

    def get_currentSetNo(self, obj):
        loading = self._get_active_loading(obj)
        return loading.sizing_outcome.set_no if loading and loading.sizing_outcome else ""

    def get_clothQuality(self, obj):
        loading = self._get_active_loading(obj)
        return loading.cloth_quality if loading else ""

    def get_clothName(self, obj):
        loading = self._get_active_loading(obj)
        if loading and loading.cloth_name:
            return getattr(loading.cloth_name, "cloth_quality", "")
        return ""

    def get_beamLength(self, obj):
        loading = self._get_active_loading(obj)
        if not loading:
            return 0.0
        beam = loading.beam
        so = loading.sizing_outcome
        if beam and beam.length:
            return float(beam.length)
        if loading.expected_length:
            return float(loading.expected_length)
        if so and so.set_length_meter:
            total_beams = so.total_beams or 1
            return round(float(so.set_length_meter) / float(total_beams), 2)
        return 0.0

    def get_producedMeters(self, obj):
        loading = self._get_active_loading(obj)
        if not loading:
            return 0.0
        from django.db.models import Sum
        patch_total = (
            loading.cloth_patches.aggregate(Sum("productive_length"))["productive_length__sum"]
            if hasattr(loading, "cloth_patches")
            else None
        )
        prod_total = (
            loading.productions.aggregate(Sum("meters_produced"))["meters_produced__sum"]
            if hasattr(loading, "productions")
            else None
        )
        total = max(float(patch_total or 0), float(prod_total or 0))
        return round(float(total), 2)

    def get_remainingMeters(self, obj):
        total_len = self.get_beamLength(obj)
        produced = self.get_producedMeters(obj)
        if total_len <= 0:
            return 0.0
        return max(0.0, round(total_len - produced, 2))

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


class LoomDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create / retrieve / update operations.
    """
    loomCode = serializers.CharField(source="loom_code")
    loomName = serializers.CharField(source="loom_name")
    modelNumber = serializers.CharField(
        source="model_number", required=False, allow_blank=True, default=""
    )
    width = serializers.DecimalField(
        max_digits=15, decimal_places=6, required=False, allow_null=True
    )
    installationDate = serializers.DateField(
        source="installation_date", required=False, allow_null=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = Loom
        fields = [
            "id",
            "loomCode",
            "loomName",
            "modelNumber",
            "width",
            "installationDate",
            "location",
            "status",
            "notes",
            "currentBeamId",
            "currentBeamNo",
            "currentLoadingId",
            "currentSetNo",
            "clothQuality",
            "clothName",
            "beamLength",
            "producedMeters",
            "remainingMeters",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt", "createdBy", "updatedBy"]

    currentBeamId = serializers.SerializerMethodField()
    currentBeamNo = serializers.SerializerMethodField()
    currentLoadingId = serializers.SerializerMethodField()
    currentSetNo = serializers.SerializerMethodField()
    clothQuality = serializers.SerializerMethodField()
    clothName = serializers.SerializerMethodField()
    beamLength = serializers.SerializerMethodField()
    producedMeters = serializers.SerializerMethodField()
    remainingMeters = serializers.SerializerMethodField()

    def _get_active_loading(self, obj):
        if not hasattr(obj, "_cached_active_loading"):
            obj._cached_active_loading = obj.beam_loadings.filter(
                status__in=["Loaded", "In Production"]
            ).first()
        return obj._cached_active_loading

    def get_currentBeamId(self, obj):
        loading = self._get_active_loading(obj)
        return loading.beam.id if loading and loading.beam else None

    def get_currentBeamNo(self, obj):
        loading = self._get_active_loading(obj)
        return loading.beam.beam_number if loading and loading.beam else None

    def get_currentLoadingId(self, obj):
        loading = self._get_active_loading(obj)
        return loading.id if loading else None

    def get_currentSetNo(self, obj):
        loading = self._get_active_loading(obj)
        return loading.sizing_outcome.set_no if loading and loading.sizing_outcome else ""

    def get_clothQuality(self, obj):
        loading = self._get_active_loading(obj)
        return loading.cloth_quality if loading else ""

    def get_clothName(self, obj):
        loading = self._get_active_loading(obj)
        if loading and loading.cloth_name:
            return getattr(loading.cloth_name, "cloth_quality", "")
        return ""

    def get_beamLength(self, obj):
        loading = self._get_active_loading(obj)
        if not loading:
            return 0.0
        beam = loading.beam
        so = loading.sizing_outcome
        if beam and beam.length:
            return float(beam.length)
        if loading.expected_length:
            return float(loading.expected_length)
        if so and so.set_length_meter:
            total_beams = so.total_beams or 1
            return round(float(so.set_length_meter) / float(total_beams), 2)
        return 0.0

    def get_producedMeters(self, obj):
        loading = self._get_active_loading(obj)
        if not loading:
            return 0.0
        from django.db.models import Sum
        patch_total = (
            loading.cloth_patches.aggregate(Sum("productive_length"))["productive_length__sum"]
            if hasattr(loading, "cloth_patches")
            else None
        )
        prod_total = (
            loading.productions.aggregate(Sum("meters_produced"))["meters_produced__sum"]
            if hasattr(loading, "productions")
            else None
        )
        total = max(float(patch_total or 0), float(prod_total or 0))
        return round(float(total), 2)

    def get_remainingMeters(self, obj):
        total_len = self.get_beamLength(obj)
        produced = self.get_producedMeters(obj)
        if total_len <= 0:
            return 0.0
        return max(0.0, round(total_len - produced, 2))

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

    def validate_loomCode(self, value):  # noqa: N802
        loom_id = self.instance.id if self.instance else None
        if (
            Loom.objects
            .filter(loom_code__iexact=value)
            .exclude(id=loom_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A loom with this code already exists."
            )
        return value

    # ------------------------------------------------------------------ #
    # Create / Update  (auto-assign created_by / updated_by)
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
