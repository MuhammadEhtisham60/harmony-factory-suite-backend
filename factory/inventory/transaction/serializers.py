"""
Serializers for the InventoryTransaction submodule.
"""

from rest_framework import serializers
from .models import InventoryTransaction
from factory.inventory.item.models import InventoryItem


class InventoryTransactionSerializer(serializers.ModelSerializer):
    """Serializer for InventoryTransaction – used for create and retrieve."""

    transactionNumber = serializers.CharField(source="transaction_number", read_only=True)
    transactionDate = serializers.DateField(source="transaction_date")
    inventoryItemId = serializers.PrimaryKeyRelatedField(
        source="inventory_item", queryset=InventoryItem.objects.all()
    )
    inventoryItemName = serializers.CharField(
        source="inventory_item.item_name", read_only=True
    )
    inventoryItemCode = serializers.CharField(
        source="inventory_item.item_code", read_only=True
    )
    transactionType = serializers.ChoiceField(
        source="transaction_type",
        choices=InventoryTransaction.TransactionTypeChoices.choices,
    )
    issuedTo = serializers.CharField(
        source="issued_to", required=False, allow_blank=True
    )
    relatedArea = serializers.CharField(
        source="related_area", required=False, allow_blank=True
    )
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = [
            "id",
            "transactionNumber",
            "transactionDate",
            "inventoryItemId",
            "inventoryItemName",
            "inventoryItemCode",
            "transactionType",
            "quantity",
            "notes",
            "issuedTo",
            "relatedArea",
            "createdBy",
            "createdAt",
        ]
        read_only_fields = [
            "id", "transactionNumber", "createdAt", "createdBy",
            "inventoryItemName", "inventoryItemCode",
        ]

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "transaction_date": "transactionDate",
            "inventory_item": "inventoryItemId",
            "inventory_item_id": "inventoryItemId",
            "item_id": "inventoryItemId",
            "transaction_type": "transactionType",
            "issued_to": "issuedTo",
            "related_area": "relatedArea",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None
