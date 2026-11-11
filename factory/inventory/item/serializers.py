"""
Serializers for the InventoryItem submodule.
"""

from rest_framework import serializers
from .models import InventoryItem
from factory.inventory.category.models import InventoryCategory
from factory.inventory.unit.models import InventoryUnit


class InventoryItemListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    itemCode = serializers.CharField(source="item_code", read_only=True)
    itemName = serializers.CharField(source="item_name")
    categoryId = serializers.PrimaryKeyRelatedField(
        source="category", queryset=InventoryCategory.objects.all()
    )
    categoryName = serializers.CharField(source="category.name", read_only=True)
    unitId = serializers.PrimaryKeyRelatedField(
        source="unit", queryset=InventoryUnit.objects.all()
    )
    unitName = serializers.CharField(source="unit.name", read_only=True)
    unitAbbreviation = serializers.CharField(source="unit.abbreviation", read_only=True)
    storageLocation = serializers.CharField(
        source="storage_location", required=False, allow_blank=True
    )
    openingStock = serializers.DecimalField(
        source="opening_stock", max_digits=12, decimal_places=4
    )
    minimumStockLevel = serializers.DecimalField(
        source="minimum_stock_level", max_digits=12, decimal_places=4, required=False
    )
    currentStock = serializers.DecimalField(
        source="current_stock", max_digits=12, decimal_places=4, read_only=True
    )
    purchasePrice = serializers.DecimalField(
        source="purchase_price", max_digits=12, decimal_places=2, required=False
    )
    preferredSupplierId = serializers.PrimaryKeyRelatedField(
        source="preferred_supplier",
        queryset=__import__(
            "factory.purchase.supplier.models", fromlist=["Supplier"]
        ).Supplier.objects.all(),
        required=False,
        allow_null=True,
    )
    preferredSupplierName = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "itemCode",
            "itemName",
            "categoryId",
            "categoryName",
            "unitId",
            "unitName",
            "unitAbbreviation",
            "description",
            "storageLocation",
            "openingStock",
            "minimumStockLevel",
            "currentStock",
            "purchasePrice",
            "preferredSupplierId",
            "preferredSupplierName",
            "status",
            "createdBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "itemCode", "currentStock", "createdAt", "updatedAt", "createdBy"]

    def get_preferredSupplierName(self, obj):
        if obj.preferred_supplier:
            return obj.preferred_supplier.supplier_name
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "item_name": "itemName",
            "category": "categoryId",
            "category_id": "categoryId",
            "unit": "unitId",
            "unit_id": "unitId",
            "storage_location": "storageLocation",
            "opening_stock": "openingStock",
            "minimum_stock_level": "minimumStockLevel",
            "purchase_price": "purchasePrice",
            "preferred_supplier": "preferredSupplierId",
            "preferred_supplier_id": "preferredSupplierId",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def create(self, validated_data):
        from factory.inventory.services import create_opening_stock_ledger

        request = self.context.get("request")
        user = request.user if request and request.user and request.user.is_authenticated else None
        if user:
            validated_data["created_by"] = user
            validated_data["updated_by"] = user

        item = InventoryItem.objects.create(**validated_data)
        create_opening_stock_ledger(item, created_by=user)
        return item

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


# Detail serializer is the same for this module
InventoryItemDetailSerializer = InventoryItemListSerializer
