"""
Serializers for B-Grade Yarn.
Excludes boxes and price entirely.
"""

from decimal import Decimal
from rest_framework import serializers
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from .models import BGradeYarn, LB_PER_KG


class BGradeYarnSerializer(serializers.ModelSerializer):
    """
    Serializer for individual B-Grade yarn records (CRUD).
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

    productionType = serializers.CharField(source="production_type", default="Self", required=False)
    cones = serializers.IntegerField(default=0, min_value=0)
    weightKg = serializers.DecimalField(source="weight_kg", max_digits=15, decimal_places=6, default=Decimal("0.000000"), required=False)
    weightLb = serializers.DecimalField(source="weight_lb", max_digits=15, decimal_places=6, default=Decimal("0.000000"), required=False)
    lotNumber = serializers.CharField(source="lot_number", allow_blank=True, default="", required=False)
    entryDate = serializers.DateField(source="entry_date", required=False)
    remarks = serializers.CharField(allow_blank=True, default="", required=False)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = BGradeYarn
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
            "cones",
            "weightKg",
            "weightLb",
            "lotNumber",
            "entryDate",
            "remarks",
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

    def get_createdBy(self, obj):
        if not obj.created_by:
            return None
        return {
            "id": obj.created_by.id,
            "username": getattr(obj.created_by, "username", ""),
            "name": getattr(obj.created_by, "get_full_name", lambda: "")() or getattr(obj.created_by, "username", ""),
        }

    def get_updatedBy(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "username": getattr(obj.updated_by, "username", ""),
            "name": getattr(obj.updated_by, "get_full_name", lambda: "")() or getattr(obj.updated_by, "username", ""),
        }

    def to_internal_value(self, data):
        ret = {}
        for key in ["yarnName", "yarn_name", "yarnNameId", "yarn_name_id"]:
            if key in data and data[key] not in (None, ""):
                val = data[key]
                if isinstance(val, int) or (isinstance(val, str) and val.strip().isdigit()):
                    ret["yarn_name"] = YarnName.objects.get(pk=int(val))
                elif isinstance(val, str) and val.strip():
                    ret["yarn_name"], _ = YarnName.objects.get_or_create(name=val.strip())
                break

        for key in ["yarnType", "yarn_type", "yarnTypeId", "yarn_type_id"]:
            if key in data and data[key] not in (None, ""):
                val = data[key]
                if isinstance(val, int) or (isinstance(val, str) and val.strip().isdigit()):
                    ret["yarn_type"] = YarnType.objects.get(pk=int(val))
                elif isinstance(val, str) and val.strip():
                    ret["yarn_type"], _ = YarnType.objects.get_or_create(name=val.strip())
                break

        for key in ["yarnCount", "yarn_count", "yarnCountId", "yarn_count_id"]:
            if key in data and data[key] not in (None, ""):
                val = data[key]
                if isinstance(val, int) or (isinstance(val, str) and val.strip().isdigit()):
                    ret["yarn_count"] = YarnCount.objects.get(pk=int(val))
                elif isinstance(val, str) and val.strip():
                    ret["yarn_count"], _ = YarnCount.objects.get_or_create(name=val.strip())
                break

        if "productionType" in data:
            ret["production_type"] = data["productionType"]
        elif "production_type" in data:
            ret["production_type"] = data["production_type"]

        if "cones" in data and data["cones"] not in (None, ""):
            ret["cones"] = int(data["cones"])

        w_kg = data.get("weightKg", data.get("weight_kg", None))
        w_lb = data.get("weightLb", data.get("weight_lb", None))

        if w_kg not in (None, ""):
            ret["weight_kg"] = Decimal(str(w_kg))
        if w_lb not in (None, ""):
            ret["weight_lb"] = Decimal(str(w_lb))

        if "lotNumber" in data:
            ret["lot_number"] = str(data["lotNumber"]).strip()
        elif "lot_number" in data:
            ret["lot_number"] = str(data["lot_number"]).strip()

        raw_date = data.get("entryDate", data.get("entry_date", None))
        if raw_date:
            if hasattr(raw_date, "date"):
                ret["entry_date"] = raw_date.date()
            elif isinstance(raw_date, str) and "T" in raw_date:
                ret["entry_date"] = raw_date.split("T")[0]
            else:
                ret["entry_date"] = raw_date

        if "remarks" in data:
            ret["remarks"] = str(data["remarks"]).strip()
        elif "notes" in data:
            ret["remarks"] = str(data["notes"]).strip()

        return ret

    def validate(self, attrs):
        if not self.instance:
            if "yarn_name" not in attrs:
                raise serializers.ValidationError({"yarnName": "Yarn name is required."})
            if "yarn_type" not in attrs:
                raise serializers.ValidationError({"yarnType": "Yarn type is required."})
            if "yarn_count" not in attrs:
                raise serializers.ValidationError({"yarnCount": "Yarn count is required."})

        w_kg = attrs.get("weight_kg")
        w_lb = attrs.get("weight_lb")
        if w_kg and not w_lb:
            attrs["weight_lb"] = (Decimal(str(w_kg)) * LB_PER_KG).quantize(Decimal("0.000001"))
        elif w_lb and not w_kg:
            attrs["weight_kg"] = (Decimal(str(w_lb)) / LB_PER_KG).quantize(Decimal("0.000001"))

        return attrs

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


class BGradeYarnQualityWiseSerializer(serializers.Serializer):
    """
    Quality-wise representation of B-grade yarn pools, matching the yarn-stock structure.
    Boxes and price are completely omitted.
    """
    id = serializers.CharField(read_only=True)
    yarnName = serializers.CharField(read_only=True)
    yarnType = serializers.CharField(read_only=True)
    yarnCount = serializers.CharField(read_only=True)
    yarnNameId = serializers.IntegerField(read_only=True)
    yarnTypeId = serializers.IntegerField(read_only=True)
    yarnCountId = serializers.IntegerField(read_only=True)
    productionType = serializers.CharField(read_only=True)

    # Aggregated balances
    totalCones = serializers.IntegerField(read_only=True)
    totalWeightKg = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    totalWeightLb = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    entriesCount = serializers.IntegerField(read_only=True)
    lotNumbers = serializers.ListField(child=serializers.CharField(), read_only=True)
    lastUpdated = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)
