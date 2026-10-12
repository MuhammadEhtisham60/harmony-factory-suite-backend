"""
Serializers for the YarnStock module.
"""

from rest_framework import serializers
from .models import YarnStock


class YarnStockMinSerializer(serializers.ModelSerializer):
    """
    Compact representation of a stock pool for select dropdowns and nested objects.
    """
    yarnName = serializers.CharField(source="yarn_name", read_only=True)
    yarnType = serializers.CharField(source="yarn_type", read_only=True)
    yarnCount = serializers.CharField(source="yarn_count", read_only=True)
    productionType = serializers.CharField(source="production_type", read_only=True)
    price = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pricePerKg = serializers.DecimalField(source="price_per_kg", max_digits=15, decimal_places=2, read_only=True)
    totalBoxes = serializers.IntegerField(source="total_boxes", read_only=True)
    cones = serializers.IntegerField(read_only=True)
    totalWeightKg = serializers.DecimalField(source="total_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    totalWeightLb = serializers.DecimalField(source="total_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    class Meta:
        model = YarnStock
        fields = [
            "id",
            "yarnName",
            "yarnType",
            "yarnCount",
            "productionType",
            "price",
            "pricePerKg",
            "totalBoxes",
            "cones",
            "totalWeightKg",
            "totalWeightLb",
        ]


class YarnStockListSerializer(serializers.ModelSerializer):
    """
    Serializer for the stock table / inventory listing page.
    """
    yarnName = serializers.CharField(source="yarn_name", read_only=True)
    yarnType = serializers.CharField(source="yarn_type", read_only=True)
    yarnCount = serializers.CharField(source="yarn_count", read_only=True)
    productionType = serializers.CharField(source="production_type", read_only=True)
    price = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pricePerKg = serializers.DecimalField(source="price_per_kg", max_digits=15, decimal_places=2, read_only=True)

    # Current available
    totalBoxes = serializers.IntegerField(source="total_boxes", read_only=True)
    cones = serializers.IntegerField(read_only=True)
    totalWeightKg = serializers.DecimalField(source="total_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    totalWeightLb = serializers.DecimalField(source="total_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    # Ledger received totals
    totalReceivedBoxes = serializers.IntegerField(source="total_received_boxes", read_only=True)
    totalReceivedCones = serializers.IntegerField(source="total_received_cones", read_only=True)
    totalReceivedWeightKg = serializers.DecimalField(source="total_received_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    totalReceivedWeightLb = serializers.DecimalField(source="total_received_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    # Ledger dispatched totals
    totalDispatchedBoxes = serializers.IntegerField(source="total_dispatched_boxes", read_only=True)
    totalDispatchedWeightKg = serializers.DecimalField(source="total_dispatched_weight_kg", max_digits=15, decimal_places=3, read_only=True)
    totalDispatchedWeightLb = serializers.DecimalField(source="total_dispatched_weight_lb", max_digits=15, decimal_places=3, read_only=True)

    intakesCount = serializers.SerializerMethodField()
    outcomesCount = serializers.SerializerMethodField()

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = YarnStock
        fields = [
            "id",
            "yarnName",
            "yarnType",
            "yarnCount",
            "productionType",
            "price",
            "pricePerKg",
            "totalBoxes",
            "cones",
            "totalWeightKg",
            "totalWeightLb",
            "totalReceivedBoxes",
            "totalReceivedCones",
            "totalReceivedWeightKg",
            "totalReceivedWeightLb",
            "totalDispatchedBoxes",
            "totalDispatchedWeightKg",
            "totalDispatchedWeightLb",
            "intakesCount",
            "outcomesCount",
            "createdAt",
            "updatedAt",
            "createdBy",
            "updatedBy",
        ]

    def get_intakesCount(self, obj):
        return obj.intakes.count()

    def get_outcomesCount(self, obj):
        return obj.outcomes.count()

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None


class YarnStockDetailSerializer(YarnStockListSerializer):
    """
    Full detail serializer for a single stock pool.
    """
    pass
