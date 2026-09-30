"""
Serializers for the Beam module.
"""

from rest_framework import serializers
from .models import Beam


class BeamListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list / table views.
    """
    beamCode = serializers.CharField(source="beam_code")
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
            "beamCode",
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
    beamCode = serializers.CharField(source="beam_code")
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
            "beamCode",
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

    def validate_beamCode(self, value):  # noqa: N802
        beam_id = self.instance.id if self.instance else None
        if (
            Beam.objects
            .filter(beam_code__iexact=value)
            .exclude(id=beam_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A beam with this code already exists."
            )
        return value

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
