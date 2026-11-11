"""
Serializers for the InventoryPurchase submodule.
"""

from decimal import Decimal
from rest_framework import serializers
from .models import InventoryPurchase, InventoryPurchaseItem
from factory.purchase.supplier.models import Supplier
from factory.inventory.item.models import InventoryItem


class InventoryPurchaseItemSerializer(serializers.ModelSerializer):
    """Line-item serializer used nested inside InventoryPurchaseSerializer."""

    inventoryItemId = serializers.PrimaryKeyRelatedField(
        source="inventory_item", queryset=InventoryItem.objects.all()
    )
    inventoryItemName = serializers.CharField(
        source="inventory_item.item_name", read_only=True
    )
    inventoryItemCode = serializers.CharField(
        source="inventory_item.item_code", read_only=True
    )
    unitPrice = serializers.DecimalField(source="unit_price", max_digits=12, decimal_places=2)
    totalPrice = serializers.DecimalField(
        source="total_price", max_digits=15, decimal_places=2, required=False
    )

    class Meta:
        model = InventoryPurchaseItem
        fields = [
            "id",
            "inventoryItemId",
            "inventoryItemName",
            "inventoryItemCode",
            "quantity",
            "unitPrice",
            "totalPrice",
        ]
        extra_kwargs = {
            "id": {"read_only": False, "required": False},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "inventory_item": "inventoryItemId",
            "inventory_item_id": "inventoryItemId",
            "item_id": "inventoryItemId",
            "unit_price": "unitPrice",
            "total_price": "totalPrice",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):
        qty = attrs.get("quantity")
        unit_price = attrs.get("unit_price")
        if qty is not None and unit_price is not None:
            if not attrs.get("total_price"):
                attrs["total_price"] = (qty * unit_price).quantize(Decimal("0.01"))
        return attrs



class InventoryPurchaseSerializer(serializers.ModelSerializer):
    """Full serializer for InventoryPurchase with nested items."""

    purchaseNumber = serializers.CharField(source="purchase_number", read_only=True)
    supplierId = serializers.PrimaryKeyRelatedField(
        source="supplier", queryset=Supplier.objects.all()
    )
    supplierName = serializers.CharField(source="supplier.supplier_name", read_only=True)
    purchaseDate = serializers.DateField(source="purchase_date")
    referenceNumber = serializers.CharField(
        source="reference_number", required=False, allow_blank=True
    )
    totalAmount = serializers.DecimalField(
        source="total_amount", max_digits=15, decimal_places=2, required=False
    )
    amountPaid = serializers.DecimalField(
        source="amount_paid", max_digits=15, decimal_places=2, required=False
    )
    amountDue = serializers.DecimalField(
        source="amount_due", max_digits=15, decimal_places=2, read_only=True
    )
    paymentStatus = serializers.CharField(
        source="payment_status", required=False, allow_blank=True
    )
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    items = InventoryPurchaseItemSerializer(many=True, required=False, default=list)

    class Meta:
        model = InventoryPurchase
        fields = [
            "id",
            "purchaseNumber",
            "supplierId",
            "supplierName",
            "purchaseDate",
            "referenceNumber",
            "notes",
            "totalAmount",
            "amountPaid",
            "amountDue",
            "paymentStatus",
            "status",
            "items",
            "createdBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id", "purchaseNumber", "amountDue", "createdAt", "updatedAt", "createdBy", "status"
        ]

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "supplier": "supplierId",
            "supplier_id": "supplierId",
            "purchase_date": "purchaseDate",
            "reference_number": "referenceNumber",
            "total_amount": "totalAmount",
            "amount_paid": "amountPaid",
            "payment_status": "paymentStatus",
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

    def _sync_items(self, purchase, items_data):
        incoming_ids = {item.get("id") for item in items_data if item.get("id")}
        purchase.items.exclude(pk__in=incoming_ids).delete()
        for item_data in items_data:
            item_id = item_data.pop("id", None)
            if item_id:
                InventoryPurchaseItem.objects.filter(pk=item_id, purchase=purchase).update(
                    **{
                        "inventory_item": item_data.get("inventory_item"),
                        "quantity": item_data.get("quantity"),
                        "unit_price": item_data.get("unit_price"),
                        "total_price": item_data.get("total_price"),
                    }
                )
            else:
                InventoryPurchaseItem.objects.create(purchase=purchase, **item_data)

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        if not validated_data.get("total_amount") or validated_data.get("total_amount") == 0:
            validated_data["total_amount"] = sum(
                (item.get("total_price", Decimal("0")) for item in items_data), Decimal("0")
            )

        explicit_status = validated_data.get("payment_status")
        purchase = InventoryPurchase(**validated_data)
        purchase.recompute_payment_fields(explicit_status=explicit_status)
        purchase.save()
        for item_data in items_data:
            item_data.pop("id", None)
            InventoryPurchaseItem.objects.create(purchase=purchase, **item_data)
        return purchase

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        explicit_status = validated_data.get("payment_status")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.recompute_payment_fields(explicit_status=explicit_status)
        instance.save()
        if items_data is not None:
            self._sync_items(instance, items_data)
        return instance
