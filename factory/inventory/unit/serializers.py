"""
Serializers for the InventoryUnit submodule.
"""

from rest_framework import serializers
from .models import InventoryUnit


class InventoryUnitSerializer(serializers.ModelSerializer):
    """Full serializer for InventoryUnit."""

    isActive = serializers.BooleanField(source="is_active", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = InventoryUnit
        fields = [
            "id",
            "name",
            "abbreviation",
            "isActive",
            "createdAt",
        ]
        read_only_fields = ["id", "createdAt"]
