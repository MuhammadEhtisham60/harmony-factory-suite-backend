"""
Serializers for the YarnBuyer module.
"""

from rest_framework import serializers
from .models import YarnBuyer


class YarnBuyerSerializer(serializers.ModelSerializer):
    """
    Full serializer for YarnBuyer CRUD.
    createdBy / updatedBy are read-only, populated from request.user.
    """
    buyerName = serializers.CharField(source="buyer_name")
    companyName = serializers.CharField(
        source="company_name", required=False, allow_blank=True, default=""
    )
    phoneNo = serializers.CharField(
        source="phone_no", required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(required=False, allow_blank=True, default="")
    country = serializers.CharField(required=False, allow_blank=True, default="Pakistan")
    status = serializers.CharField(required=False, default="Active")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = YarnBuyer
        fields = [
            "id",
            "buyerName",
            "companyName",
            "phoneNo",
            "email",
            "address",
            "city",
            "country",
            "status",
            "notes",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "createdAt", "updatedAt", "createdBy", "updatedBy"]

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None

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
