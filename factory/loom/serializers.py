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
    loomType = serializers.CharField(
        source="loom_type", required=False, allow_blank=True
    )
    modelNumber = serializers.CharField(
        source="model_number", required=False, allow_blank=True
    )
    serialNumber = serializers.CharField(
        source="serial_number", required=False, allow_null=True, allow_blank=True
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
            "loomType",
            "manufacturer",
            "modelNumber",
            "serialNumber",
            "width",
            "installationDate",
            "location",
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


class LoomDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create / retrieve / update operations.
    """
    loomCode = serializers.CharField(source="loom_code")
    loomName = serializers.CharField(source="loom_name")
    loomType = serializers.CharField(
        source="loom_type", required=False, allow_blank=True, default=""
    )
    modelNumber = serializers.CharField(
        source="model_number", required=False, allow_blank=True, default=""
    )
    serialNumber = serializers.CharField(
        source="serial_number", required=False, allow_null=True, allow_blank=True
    )
    width = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
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
            "loomType",
            "manufacturer",
            "modelNumber",
            "serialNumber",
            "width",
            "installationDate",
            "location",
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

    def validate_serialNumber(self, value):  # noqa: N802
        if not value:
            return value
        loom_id = self.instance.id if self.instance else None
        if (
            Loom.objects
            .filter(serial_number__iexact=value)
            .exclude(id=loom_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A loom with this serial number already exists."
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
