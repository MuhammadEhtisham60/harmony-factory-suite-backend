"""
Serializers for the InventoryCategory submodule.
"""

from rest_framework import serializers
from .models import InventoryCategory


class InventoryCategorySerializer(serializers.ModelSerializer):
    """Full serializer for InventoryCategory – create / retrieve / update."""

    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = InventoryCategory
        fields = [
            "id",
            "name",
            "description",
            "isActive",
            "createdBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt", "createdBy"]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)
