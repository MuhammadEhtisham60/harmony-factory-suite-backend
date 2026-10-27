"""
Serializers for Warping master module.
"""

from rest_framework import serializers
from .models import Warping


class WarpingMinSerializer(serializers.ModelSerializer):
    """Minimal Warping details for nested responses."""
    warpingName = serializers.CharField(source="warping_name")
    contactPerson = serializers.CharField(source="contact_person")
    phoneNo = serializers.CharField(source="phone_no")

    class Meta:
        model = Warping
        fields = ["id", "warpingName", "contactPerson", "phoneNo", "status"]


class WarpingSerializer(serializers.ModelSerializer):
    """Full serializer for Warping unit CRUD."""
    warpingName = serializers.CharField(source="warping_name")
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
        choices=Warping.StatusChoices.choices,
        required=False,
        default=Warping.StatusChoices.ACTIVE,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = Warping
        fields = [
            "id",
            "warpingName",
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
