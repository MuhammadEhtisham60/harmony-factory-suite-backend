"""
Serializers for the YarnStock module.
"""

from rest_framework import serializers
from .models import YarnStock


class YarnStockMinSerializer(serializers.ModelSerializer):
    """
    Compact representation of a stock pool for select dropdowns and nested objects.
    """
    yarnName = serializers.SerializerMethodField()
    yarnType = serializers.SerializerMethodField()
    yarnCount = serializers.SerializerMethodField()
    yarnNameId = serializers.IntegerField(source="yarn_name_id", read_only=True)
    yarnTypeId = serializers.IntegerField(source="yarn_type_id", read_only=True)
    yarnCountId = serializers.IntegerField(source="yarn_count_id", read_only=True)
    yarnNameDetail = serializers.SerializerMethodField()
    yarnTypeDetail = serializers.SerializerMethodField()
    yarnCountDetail = serializers.SerializerMethodField()
    productionType = serializers.CharField(source="production_type", read_only=True)
    price = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    totalPrice = serializers.DecimalField(source="total_price", max_digits=18, decimal_places=6, read_only=True)
    pricePerKg = serializers.DecimalField(source="price_per_kg", max_digits=15, decimal_places=6, read_only=True)
    totalBoxes = serializers.IntegerField(source="total_boxes", read_only=True)
    cones = serializers.IntegerField(read_only=True)
    totalWeightKg = serializers.DecimalField(source="total_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    totalWeightLb = serializers.DecimalField(source="total_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    class Meta:
        model = YarnStock
        fields = [
            "id",
            "yarnName",
            "yarnType",
            "yarnCount",
            "yarnNameId",
            "yarnTypeId",
            "yarnCountId",
            "yarnNameDetail",
            "yarnTypeDetail",
            "yarnCountDetail",
            "productionType",
            "price",
            "totalPrice",
            "pricePerKg",
            "totalBoxes",
            "cones",
            "totalWeightKg",
            "totalWeightLb",
        ]

    def get_yarnName(self, obj):
        return obj.yarn_name.name if obj.yarn_name else ""

    def get_yarnType(self, obj):
        return obj.yarn_type.name if obj.yarn_type else ""

    def get_yarnCount(self, obj):
        return obj.yarn_count.name if obj.yarn_count else ""

    def get_yarnNameDetail(self, obj):
        return {"id": obj.yarn_name.id, "name": obj.yarn_name.name} if obj.yarn_name else None

    def get_yarnTypeDetail(self, obj):
        return {"id": obj.yarn_type.id, "name": obj.yarn_type.name} if obj.yarn_type else None

    def get_yarnCountDetail(self, obj):
        return {"id": obj.yarn_count.id, "name": obj.yarn_count.name} if obj.yarn_count else None


class YarnStockListSerializer(serializers.ModelSerializer):
    """
    Serializer for the stock table / inventory listing page.
    """
    yarnName = serializers.SerializerMethodField()
    yarnType = serializers.SerializerMethodField()
    yarnCount = serializers.SerializerMethodField()
    yarnNameId = serializers.IntegerField(source="yarn_name_id", read_only=True)
    yarnTypeId = serializers.IntegerField(source="yarn_type_id", read_only=True)
    yarnCountId = serializers.IntegerField(source="yarn_count_id", read_only=True)
    yarnNameDetail = serializers.SerializerMethodField()
    yarnTypeDetail = serializers.SerializerMethodField()
    yarnCountDetail = serializers.SerializerMethodField()
    productionType = serializers.CharField(source="production_type", read_only=True)
    price = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    totalPrice = serializers.DecimalField(source="total_price", max_digits=18, decimal_places=6, read_only=True)
    pricePerKg = serializers.DecimalField(source="price_per_kg", max_digits=15, decimal_places=6, read_only=True)

    # Current available
    totalBoxes = serializers.IntegerField(source="total_boxes", read_only=True)
    cones = serializers.IntegerField(read_only=True)
    totalWeightKg = serializers.DecimalField(source="total_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    totalWeightLb = serializers.DecimalField(source="total_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    # Ledger received totals
    totalReceivedBoxes = serializers.IntegerField(source="total_received_boxes", read_only=True)
    totalReceivedCones = serializers.IntegerField(source="total_received_cones", read_only=True)
    totalReceivedWeightKg = serializers.DecimalField(source="total_received_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    totalReceivedWeightLb = serializers.DecimalField(source="total_received_weight_lb", max_digits=15, decimal_places=6, read_only=True)

    # Ledger dispatched totals
    totalDispatchedBoxes = serializers.IntegerField(source="total_dispatched_boxes", read_only=True)
    totalDispatchedWeightKg = serializers.DecimalField(source="total_dispatched_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    totalDispatchedWeightLb = serializers.DecimalField(source="total_dispatched_weight_lb", max_digits=15, decimal_places=6, read_only=True)

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
            "yarnNameId",
            "yarnTypeId",
            "yarnCountId",
            "yarnNameDetail",
            "yarnTypeDetail",
            "yarnCountDetail",
            "productionType",
            "price",
            "totalPrice",
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

    def get_yarnName(self, obj):
        return obj.yarn_name.name if obj.yarn_name else ""

    def get_yarnType(self, obj):
        return obj.yarn_type.name if obj.yarn_type else ""

    def get_yarnCount(self, obj):
        return obj.yarn_count.name if obj.yarn_count else ""

    def get_yarnNameDetail(self, obj):
        return {"id": obj.yarn_name.id, "name": obj.yarn_name.name} if obj.yarn_name else None

    def get_yarnTypeDetail(self, obj):
        return {"id": obj.yarn_type.id, "name": obj.yarn_type.name} if obj.yarn_type else None

    def get_yarnCountDetail(self, obj):
        return {"id": obj.yarn_count.id, "name": obj.yarn_count.name} if obj.yarn_count else None

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
