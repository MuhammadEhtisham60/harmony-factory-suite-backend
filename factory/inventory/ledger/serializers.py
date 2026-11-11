"""
Serializers for the InventoryLedger and InventoryPayment submodule.
"""

from rest_framework import serializers
from .models import InventoryLedger, InventoryPayment


class InventoryPaymentSerializer(serializers.ModelSerializer):
    """Read serializer for InventoryPayment records."""

    ledgerEntryId = serializers.IntegerField(source="ledger_entry_id", read_only=True)
    purchaseId = serializers.IntegerField(source="purchase_id", read_only=True)
    supplierId = serializers.IntegerField(source="supplier_id", read_only=True)
    supplierName = serializers.SerializerMethodField()
    bankAccountId = serializers.IntegerField(source="bank_account_id", read_only=True)
    bankAccountName = serializers.SerializerMethodField()
    paymentDate = serializers.DateField(source="payment_date", read_only=True)
    paymentMethod = serializers.CharField(source="payment_method", read_only=True)
    referenceNumber = serializers.CharField(source="reference_number", read_only=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = InventoryPayment
        fields = [
            "id",
            "ledgerEntryId",
            "purchaseId",
            "supplierId",
            "supplierName",
            "bankAccountId",
            "bankAccountName",
            "amount",
            "paymentDate",
            "paymentMethod",
            "referenceNumber",
            "notes",
            "createdBy",
            "createdAt",
        ]

    def get_supplierName(self, obj):
        if obj.supplier:
            return obj.supplier.supplier_name
        return None

    def get_bankAccountName(self, obj):
        if obj.bank_account:
            return f"{obj.bank_account.bank_name} - {obj.bank_account.account_title}"
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None


class InventoryLedgerSerializer(serializers.ModelSerializer):
    """Serializer for InventoryLedger entries including financial & payment status."""

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
    unitPrice = serializers.DecimalField(
        source="unit_price", max_digits=12, decimal_places=2, read_only=True
    )
    totalAmount = serializers.DecimalField(
        source="total_amount", max_digits=15, decimal_places=2, read_only=True
    )
    amountPaid = serializers.DecimalField(
        source="amount_paid", max_digits=15, decimal_places=2, read_only=True
    )
    amountDue = serializers.DecimalField(
        source="amount_due", max_digits=15, decimal_places=2, read_only=True
    )
    paymentStatus = serializers.CharField(source="payment_status", read_only=True)
    referenceId = serializers.IntegerField(source="reference_id", read_only=True)
    referenceType = serializers.CharField(source="reference_type", read_only=True)
    supplierId = serializers.IntegerField(source="supplier_id", read_only=True)
    supplierName = serializers.SerializerMethodField()
    payments = InventoryPaymentSerializer(many=True, read_only=True)
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
            "unitPrice",
            "totalAmount",
            "amountPaid",
            "amountDue",
            "paymentStatus",
            "referenceId",
            "referenceType",
            "supplierId",
            "supplierName",
            "notes",
            "payments",
            "createdBy",
            "createdAt",
        ]

    def get_supplierName(self, obj):
        if obj.supplier:
            return obj.supplier.supplier_name
        if obj.inventory_item and obj.inventory_item.preferred_supplier:
            return obj.inventory_item.preferred_supplier.supplier_name
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

