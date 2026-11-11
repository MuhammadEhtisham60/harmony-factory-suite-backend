"""
Serializers for the InventoryLedger submodule.
"""

from rest_framework import serializers
from .models import InventoryLedger


class InventoryLedgerSerializer(serializers.ModelSerializer):
    """Read-only serializer for InventoryLedger entries."""

    inventoryItemId = serializers.IntegerField(source="inventory_item_id", read_only=True)
    inventoryItemName = serializers.CharField(
        source="inventory_item.item_name", read_only=True
    )
    inventoryItemCode = serializers.CharField(
        source="inventory_item.item_code", read_only=True
    )
    unit = serializers.CharField(
        source="inventory_item.unit.abbreviation", read_only=True
    )
    transactionDate = serializers.DateField(source="transaction_date", read_only=True)
    transactionNumber = serializers.CharField(source="transaction_number", read_only=True)
    transactionType = serializers.CharField(source="transaction_type", read_only=True)
    quantityIn = serializers.DecimalField(
        source="quantity_in", max_digits=12, decimal_places=4, read_only=True
    )
    quantityOut = serializers.DecimalField(
        source="quantity_out", max_digits=12, decimal_places=4, read_only=True
    )
    runningBalance = serializers.DecimalField(
        source="running_balance", max_digits=12, decimal_places=4, read_only=True
    )
    referenceId = serializers.IntegerField(source="reference_id", read_only=True)
    referenceType = serializers.CharField(source="reference_type", read_only=True)
    supplierId = serializers.IntegerField(source="supplier_id", read_only=True)
    supplierName = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = InventoryLedger
        fields = [
            "id",
            "inventoryItemId",
            "inventoryItemName",
            "inventoryItemCode",
            "unit",
            "transactionDate",
            "transactionNumber",
            "transactionType",
            "quantityIn",
            "quantityOut",
            "runningBalance",
            "referenceId",
            "referenceType",
            "supplierId",
            "supplierName",
            "notes",
            "createdBy",
            "createdAt",
        ]

    def get_supplierName(self, obj):
        if obj.supplier:
            return obj.supplier.supplier_name
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None
