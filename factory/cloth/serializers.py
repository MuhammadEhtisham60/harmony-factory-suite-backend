"""
Serializers for Cloth Production and Inventory.

Provides:
- Dual camelCase and snake_case API compatibility.
- Comprehensive validations (positive lengths, loading status, allocation constraints).
- Optimized nested representations avoiding N+1 queries.
- Clean audit fields.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.beam.models import Beam, BeamLoading
from factory.loom.models import Loom
from .models import (
    ClothName,
    ClothPatch,
    ClothStock,
    CleanClothStock,
    DefectedClothStock,
)
from .services import (
    create_cloth_patch,
    create_clean_cloth_stock,
    update_clean_cloth_stock,
    create_defected_cloth_stock,
    update_defected_cloth_stock,
    validate_patch_allocation,
)


class ClothNameSerializer(serializers.ModelSerializer):
    """
    Serializer for ClothName master model.
    Normalizes whitespace and rejects case-insensitive duplicates.
    """
    name = serializers.CharField(max_length=150)
    warpCount = serializers.CharField(source="warp_count", required=False, allow_blank=True, default="")
    warp_count = serializers.CharField(read_only=True)
    weftCount = serializers.CharField(source="weft_count", required=False, allow_blank=True, default="")
    weft_count = serializers.CharField(read_only=True)
    reedCount = serializers.DecimalField(source="reed_count", max_digits=15, decimal_places=6, required=False, allow_null=True)
    reed_count = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    pickCount = serializers.DecimalField(source="pick_count", max_digits=15, decimal_places=6, required=False, allow_null=True)
    pick_count = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    reedWidth = serializers.DecimalField(source="reed_width", max_digits=15, decimal_places=6, required=False, allow_null=True)
    reed_width = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = ClothName
        fields = [
            "id",
            "name",
            "warpCount",
            "warp_count",
            "weftCount",
            "weft_count",
            "reedCount",
            "reed_count",
            "pickCount",
            "pick_count",
            "reedWidth",
            "reed_width",
            "description",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]
        read_only_fields = [
            "id",
            "warp_count",
            "weft_count",
            "reed_count",
            "pick_count",
            "reed_width",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "warp_count": "warpCount",
            "weft_count": "weftCount",
            "reed_count": "reedCount",
            "pick_count": "pickCount",
            "reed_width": "reedWidth",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data.pop(snake)

        for field in ("reedCount", "pickCount", "reedWidth"):
            if field in data and (data[field] == "" or data[field] is None):
                data[field] = None

        return super().to_internal_value(data)

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def validate_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Cloth name cannot be blank.")
        qs = ClothName.objects.filter(name__iexact=cleaned)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(f"Cloth name '{cleaned}' already exists (case-insensitive).")
        return cleaned

    def create(self, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        validated_data["created_by"] = user
        validated_data["updated_by"] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        if user:
            validated_data["updated_by"] = user
        return super().update(instance, validated_data)


def _format_cloth_name_summary(cn):
    if not cn:
        return None
    return {
        "id": cn.id,
        "name": cn.name,
        "warpCount": cn.warp_count,
        "weftCount": cn.weft_count,
        "reedCount": cn.reed_count,
        "pickCount": cn.pick_count,
        "reedWidth": cn.reed_width,
    }


class ClothPatchSerializer(serializers.ModelSerializer):
    """
    Serializer for ClothPatch (used by both ClothPatchViewSet and Raw Stock screen).
    Supports individual patch creation, rich nested loom/beam/loading details,
    and allocation metrics.
    """
    patchNumber = serializers.CharField(source="patch_number", required=False, allow_blank=True)
    patch_number = serializers.CharField(required=False, allow_blank=True)

    setNo = serializers.CharField(source="set_no", required=False, allow_blank=True)
    set_no = serializers.CharField(required=False, allow_blank=True)

    clothName = serializers.SerializerMethodField()
    cloth_name = serializers.PrimaryKeyRelatedField(
        queryset=ClothName.objects.all(),
        required=False,
    )
    clothNameId = serializers.IntegerField(source="cloth_name_id", required=False, write_only=True)

    loom = serializers.PrimaryKeyRelatedField(
        queryset=Loom.objects.all(),
        required=False,
    )
    loomId = serializers.IntegerField(source="loom_id", required=False, write_only=True)
    loomDetail = serializers.SerializerMethodField()

    beam = serializers.PrimaryKeyRelatedField(
        queryset=Beam.objects.all(),
        required=False,
    )
    beamId = serializers.IntegerField(source="beam_id", required=False, write_only=True)
    beamDetail = serializers.SerializerMethodField()

    beamLoading = serializers.PrimaryKeyRelatedField(
        source="beam_loading",
        queryset=BeamLoading.objects.all(),
        required=False,
    )
    beamLoadingId = serializers.IntegerField(source="beam_loading_id", required=False, write_only=True)
    beam_loading = serializers.PrimaryKeyRelatedField(
        queryset=BeamLoading.objects.all(),
        required=False,
    )

    patchDate = serializers.DateField(source="patch_date")
    patch_date = serializers.DateField(required=False)

    bundleCount = serializers.IntegerField(source="bundle_count", default=1)
    bundle_count = serializers.IntegerField(required=False, default=1)

    productiveLength = serializers.DecimalField(source="productive_length", max_digits=15, decimal_places=6)
    productive_length = serializers.DecimalField(max_digits=15, decimal_places=6, required=False)

    cleanAllocatedLength = serializers.DecimalField(source="clean_allocated_length", max_digits=15, decimal_places=6, read_only=True)
    clean_allocated_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    defectedAllocatedLength = serializers.DecimalField(source="defected_allocated_length", max_digits=15, decimal_places=6, read_only=True)
    defected_allocated_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    classifiedLength = serializers.DecimalField(source="classified_length", max_digits=15, decimal_places=6, read_only=True)
    classified_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    unallocatedLength = serializers.DecimalField(source="unallocated_length", max_digits=15, decimal_places=6, read_only=True)
    unallocated_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)

    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = ClothPatch
        fields = [
            "id",
            "patchNumber",
            "patch_number",
            "setNo",
            "set_no",
            "clothName",
            "cloth_name",
            "clothNameId",
            "loom",
            "loomId",
            "loomDetail",
            "beam",
            "beamId",
            "beamDetail",
            "beamLoading",
            "beamLoadingId",
            "beam_loading",
            "patchDate",
            "patch_date",
            "bundleCount",
            "bundle_count",
            "productiveLength",
            "productive_length",
            "cleanAllocatedLength",
            "clean_allocated_length",
            "defectedAllocatedLength",
            "defected_allocated_length",
            "classifiedLength",
            "classified_length",
            "unallocatedLength",
            "unallocated_length",
            "remarks",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]
        read_only_fields = [
            "id",
            "cleanAllocatedLength",
            "clean_allocated_length",
            "defectedAllocatedLength",
            "defected_allocated_length",
            "classifiedLength",
            "classified_length",
            "unallocatedLength",
            "unallocated_length",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]

    def get_clothName(self, obj):
        return _format_cloth_name_summary(obj.cloth_name)

    def get_loomDetail(self, obj):
        if obj.loom:
            return {
                "id": obj.loom.id,
                "loomCode": obj.loom.loom_code,
                "loom_code": obj.loom.loom_code,
                "loomName": obj.loom.loom_name,
                "status": obj.loom.status,
            }
        return None

    def get_beamDetail(self, obj):
        if obj.beam:
            return {
                "id": obj.beam.id,
                "beamNumber": obj.beam.beam_number,
                "beam_number": obj.beam.beam_number,
                "beamName": obj.beam.beam_name,
                "status": obj.beam.status,
            }
        return None

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "patch_number": "patchNumber",
            "set_no": "setNo",
            "cloth_name": "clothName",
            "cloth_name_id": "clothNameId",
            "loom_id": "loomId",
            "beam_id": "beamId",
            "beam_loading_id": "beamLoadingId",
            "beam_loading": "beamLoading",
            "patch_date": "patchDate",
            "bundle_count": "bundleCount",
            "productive_length": "productiveLength",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Resolve beamLoading
        loading = attrs.get("beam_loading")
        loading_id = (
            self.initial_data.get("beam_loading")
            or self.initial_data.get("beam_loading_id")
            or self.initial_data.get("beamLoading")
            or self.initial_data.get("beamLoadingId")
        )
        if not loading and loading_id:
            try:
                attrs["beam_loading"] = BeamLoading.objects.get(id=loading_id)
            except BeamLoading.DoesNotExist:
                raise serializers.ValidationError({"beamLoading": [f"BeamLoading #{loading_id} does not exist."]})
        elif not loading and not self.instance:
            raise serializers.ValidationError({"beamLoading": ["beam_loading (or beamLoadingId) is required."]})

        resolved_loading = attrs.get("beam_loading") or (self.instance.beam_loading if self.instance else None)

        # Resolve loom
        loom = attrs.get("loom")
        loom_id = self.initial_data.get("loom") or self.initial_data.get("loom_id") or self.initial_data.get("loomId")
        if not loom and loom_id:
            try:
                attrs["loom"] = Loom.objects.get(id=loom_id)
            except Loom.DoesNotExist:
                raise serializers.ValidationError({"loom": [f"Loom #{loom_id} does not exist."]})
        elif not loom and not self.instance and resolved_loading:
            attrs["loom"] = resolved_loading.loom

        # Resolve beam
        beam = attrs.get("beam")
        beam_id = self.initial_data.get("beam") or self.initial_data.get("beam_id") or self.initial_data.get("beamId")
        if not beam and beam_id:
            try:
                attrs["beam"] = Beam.objects.get(id=beam_id)
            except Beam.DoesNotExist:
                raise serializers.ValidationError({"beam": [f"Beam #{beam_id} does not exist."]})
        elif not beam and not self.instance and resolved_loading:
            attrs["beam"] = resolved_loading.beam

        # Resolve clothName
        cloth_name = attrs.get("cloth_name")
        cn_id = self.initial_data.get("cloth_name") or self.initial_data.get("cloth_name_id") or self.initial_data.get("clothNameId")
        if not cloth_name and cn_id:
            try:
                attrs["cloth_name"] = ClothName.objects.get(id=cn_id)
            except ClothName.DoesNotExist:
                raise serializers.ValidationError({"clothName": [f"ClothName #{cn_id} does not exist."]})
        elif not cloth_name and not self.instance:
            # Check by cloth_name string if provided
            cn_str = self.initial_data.get("clothName") or self.initial_data.get("cloth_name")
            if isinstance(cn_str, str) and cn_str.strip():
                cn_obj = ClothName.objects.filter(name__iexact=cn_str.strip()).first()
                if not cn_obj:
                    cn_obj = ClothName.objects.create(name=cn_str.strip())
                attrs["cloth_name"] = cn_obj
            elif resolved_loading and getattr(resolved_loading, "cloth_name", None):
                attrs["cloth_name"] = resolved_loading.cloth_name
            elif resolved_loading and getattr(resolved_loading, "cloth_quality", None):
                cn_obj, _ = ClothName.objects.get_or_create(name=resolved_loading.cloth_quality.strip())
                attrs["cloth_name"] = cn_obj
            else:
                raise serializers.ValidationError({"clothName": ["cloth_name (or clothNameId) is required."]})

        # Productive length check
        length = attrs.get("productive_length")
        if length is not None and length <= Decimal("0.000000"):
            raise serializers.ValidationError({"productiveLength": ["Productive length must be strictly positive (> 0)."]})

        # In case of update, ensure productive_length is not reduced below already classified length
        if self.instance and length is not None:
            classified = self.instance.classified_length
            if length < classified:
                raise serializers.ValidationError({
                    "productiveLength": [
                        f"Cannot reduce productive length to {length}m because {classified}m has already "
                        f"been classified into clean/defected stock."
                    ]
                })

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        patch = create_cloth_patch(
            beam_loading_or_id=validated_data["beam_loading"],
            patch_number=validated_data.get("patch_number", ""),
            cloth_name_or_id=validated_data["cloth_name"],
            patch_date=validated_data["patch_date"],
            productive_length=validated_data["productive_length"],
            bundle_count=validated_data.get("bundle_count", 1),
            loom_or_id=validated_data.get("loom"),
            beam_or_id=validated_data.get("beam"),
            set_no=validated_data.get("set_no", ""),
            remarks=validated_data.get("remarks", ""),
            user=user,
            request=self.context.get("request"),
        )
        return patch

    def update(self, instance, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if user:
            instance.updated_by = user
        instance.save()
        return instance


class ClothStockSerializer(serializers.ModelSerializer):
    """
    Consolidated Cloth Stock serializer for the Cloth Stock screen.
    Returns:
      - cloth_name: { "id": ..., "name": ... }
      - total_length: clean stock total
      - defected_total_length: defective stock total
      - clean_record_count: number of clean stock entries
      - defected_record_count: number of defective stock entries
    """
    cloth_name = serializers.SerializerMethodField()
    clothName = serializers.SerializerMethodField()
    cloth_name_id = serializers.IntegerField(read_only=True)
    clothNameId = serializers.IntegerField(source="cloth_name_id", read_only=True)

    total_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    totalLength = serializers.DecimalField(source="total_length", max_digits=15, decimal_places=6, read_only=True)

    defected_total_length = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    defectedTotalLength = serializers.DecimalField(source="defected_total_length", max_digits=15, decimal_places=6, read_only=True)

    clean_record_count = serializers.IntegerField(read_only=True)
    cleanRecordCount = serializers.IntegerField(source="clean_record_count", read_only=True)

    defected_record_count = serializers.IntegerField(read_only=True)
    defectedRecordCount = serializers.IntegerField(source="defected_record_count", read_only=True)

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ClothStock
        fields = [
            "id",
            "cloth_name",
            "clothName",
            "cloth_name_id",
            "clothNameId",
            "total_length",
            "totalLength",
            "defected_total_length",
            "defectedTotalLength",
            "clean_record_count",
            "cleanRecordCount",
            "defected_record_count",
            "defectedRecordCount",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_cloth_name(self, obj):
        return _format_cloth_name_summary(obj.cloth_name)

    def get_clothName(self, obj):
        return self.get_cloth_name(obj)


class CleanClothStockSerializer(serializers.ModelSerializer):
    """
    Serializer for CleanClothStock individual detail records.
    Validates allocation invariant and links directly to ClothStock and ClothPatch.
    """
    clothStock = serializers.PrimaryKeyRelatedField(
        source="cloth_stock",
        queryset=ClothStock.objects.all(),
        required=False,
    )
    clothStockId = serializers.IntegerField(source="cloth_stock_id", required=False, write_only=True)
    cloth_stock = serializers.PrimaryKeyRelatedField(
        queryset=ClothStock.objects.all(),
        required=False,
    )

    clothName = serializers.SerializerMethodField()
    cloth_name = serializers.SerializerMethodField()

    clothPatch = serializers.PrimaryKeyRelatedField(
        source="cloth_patch",
        queryset=ClothPatch.objects.all(),
        required=False,
    )
    clothPatchId = serializers.IntegerField(source="cloth_patch_id", required=False, write_only=True)
    cloth_patch = serializers.PrimaryKeyRelatedField(
        queryset=ClothPatch.objects.all(),
        required=False,
    )

    patchNumber = serializers.SerializerMethodField()
    patch_number = serializers.SerializerMethodField()

    patchProductiveLength = serializers.SerializerMethodField()
    patch_productive_length = serializers.SerializerMethodField()

    totalLength = serializers.DecimalField(source="total_length", max_digits=15, decimal_places=6)
    total_length = serializers.DecimalField(max_digits=15, decimal_places=6, required=False)

    stockDate = serializers.DateField(source="stock_date")
    stock_date = serializers.DateField(required=False)

    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = CleanClothStock
        fields = [
            "id",
            "clothStock",
            "clothStockId",
            "cloth_stock",
            "clothName",
            "cloth_name",
            "clothPatch",
            "clothPatchId",
            "cloth_patch",
            "patchNumber",
            "patch_number",
            "patchProductiveLength",
            "patch_productive_length",
            "totalLength",
            "total_length",
            "stockDate",
            "stock_date",
            "remarks",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]
        read_only_fields = [
            "id",
            "clothName",
            "cloth_name",
            "patchNumber",
            "patch_number",
            "patchProductiveLength",
            "patch_productive_length",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]

    def get_clothName(self, obj):
        if obj.cloth_stock:
            return _format_cloth_name_summary(obj.cloth_stock.cloth_name)
        return None

    def get_cloth_name(self, obj):
        return self.get_clothName(obj)

    def get_patchNumber(self, obj):
        return obj.cloth_patch.patch_number if obj.cloth_patch else ""

    def get_patch_number(self, obj):
        return self.get_patchNumber(obj)

    def get_patchProductiveLength(self, obj):
        return str(obj.cloth_patch.productive_length) if obj.cloth_patch else "0.000000"

    def get_patch_productive_length(self, obj):
        return self.get_patchProductiveLength(obj)

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "cloth_stock": "clothStock",
            "cloth_stock_id": "clothStockId",
            "cloth_patch": "clothPatch",
            "cloth_patch_id": "clothPatchId",
            "total_length": "totalLength",
            "stock_date": "stockDate",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Resolve clothPatch
        patch = attrs.get("cloth_patch")
        patch_id = (
            self.initial_data.get("cloth_patch")
            or self.initial_data.get("cloth_patch_id")
            or self.initial_data.get("clothPatch")
            or self.initial_data.get("clothPatchId")
        )
        if not patch and patch_id:
            try:
                attrs["cloth_patch"] = ClothPatch.objects.get(id=patch_id)
            except ClothPatch.DoesNotExist:
                raise serializers.ValidationError({"clothPatch": [f"ClothPatch #{patch_id} does not exist."]})
        elif not patch and not self.instance:
            raise serializers.ValidationError({"clothPatch": ["cloth_patch is required."]})

        resolved_patch = attrs.get("cloth_patch") or (self.instance.cloth_patch if self.instance else None)

        # Resolve clothStock
        stock = attrs.get("cloth_stock")
        stock_id = (
            self.initial_data.get("cloth_stock")
            or self.initial_data.get("cloth_stock_id")
            or self.initial_data.get("clothStock")
            or self.initial_data.get("clothStockId")
        )
        if not stock and stock_id:
            try:
                attrs["cloth_stock"] = ClothStock.objects.get(id=stock_id)
            except ClothStock.DoesNotExist:
                raise serializers.ValidationError({"clothStock": [f"ClothStock #{stock_id} does not exist."]})
        elif not stock and not self.instance:
            # Auto-link or auto-create ClothStock for the patch's cloth_name if omitted
            if resolved_patch and resolved_patch.cloth_name:
                stock_obj, _ = ClothStock.objects.get_or_create(
                    cloth_name=resolved_patch.cloth_name,
                    defaults={"total_length": Decimal("0.000000")}
                )
                attrs["cloth_stock"] = stock_obj
            else:
                raise serializers.ValidationError({"clothStock": ["cloth_stock is required."]})

        resolved_stock = attrs.get("cloth_stock") or (self.instance.cloth_stock if self.instance else None)

        # Validate cloth_name consistency
        if resolved_stock and resolved_patch:
            if resolved_stock.cloth_name_id != resolved_patch.cloth_name_id:
                raise serializers.ValidationError({
                    "clothStock": [
                        f"ClothStock cloth name '{resolved_stock.cloth_name.name}' does not match "
                        f"ClothPatch cloth name '{resolved_patch.cloth_name.name}'."
                    ]
                })

        # Length validation
        length = attrs.get("total_length")
        if length is not None:
            if length <= Decimal("0.000000"):
                raise serializers.ValidationError({"totalLength": ["Total length must be strictly positive (> 0)."]})
            # Check allocation invariant
            validate_patch_allocation(
                cloth_patch=resolved_patch,
                new_length=length,
                cloth_stock=resolved_stock,
                exclude_clean_id=self.instance.id if self.instance else None,
            )

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        return create_clean_cloth_stock(
            cloth_stock_or_id=validated_data["cloth_stock"],
            cloth_patch_or_id=validated_data["cloth_patch"],
            total_length=validated_data["total_length"],
            stock_date=validated_data["stock_date"],
            remarks=validated_data.get("remarks", ""),
            user=user,
            request=self.context.get("request"),
        )

    def update(self, instance, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        return update_clean_cloth_stock(
            clean_stock_or_id=instance,
            total_length=validated_data.get("total_length"),
            stock_date=validated_data.get("stock_date"),
            remarks=validated_data.get("remarks"),
            user=user,
            request=self.context.get("request"),
        )


class DefectedClothStockSerializer(serializers.ModelSerializer):
    """
    Serializer for DefectedClothStock individual detail records.
    Validates positive lengths, non-empty defect types, and allocation limits.
    """
    clothStock = serializers.PrimaryKeyRelatedField(
        source="cloth_stock",
        queryset=ClothStock.objects.all(),
        required=False,
    )
    clothStockId = serializers.IntegerField(source="cloth_stock_id", required=False, write_only=True)
    cloth_stock = serializers.PrimaryKeyRelatedField(
        queryset=ClothStock.objects.all(),
        required=False,
    )

    clothName = serializers.SerializerMethodField()
    cloth_name = serializers.SerializerMethodField()

    clothPatch = serializers.PrimaryKeyRelatedField(
        source="cloth_patch",
        queryset=ClothPatch.objects.all(),
        required=False,
    )
    clothPatchId = serializers.IntegerField(source="cloth_patch_id", required=False, write_only=True)
    cloth_patch = serializers.PrimaryKeyRelatedField(
        queryset=ClothPatch.objects.all(),
        required=False,
    )

    patchNumber = serializers.SerializerMethodField()
    patch_number = serializers.SerializerMethodField()

    patchProductiveLength = serializers.SerializerMethodField()
    patch_productive_length = serializers.SerializerMethodField()

    defectType = serializers.CharField(source="defect_type")
    defect_type = serializers.CharField(required=False)

    defectDescription = serializers.CharField(source="defect_description", required=False, allow_blank=True, default="")
    defect_description = serializers.CharField(required=False, allow_blank=True, default="")

    totalLength = serializers.DecimalField(source="total_length", max_digits=15, decimal_places=6)
    total_length = serializers.DecimalField(max_digits=15, decimal_places=6, required=False)

    stockDate = serializers.DateField(source="stock_date")
    stock_date = serializers.DateField(required=False)

    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = DefectedClothStock
        fields = [
            "id",
            "clothStock",
            "clothStockId",
            "cloth_stock",
            "clothName",
            "cloth_name",
            "clothPatch",
            "clothPatchId",
            "cloth_patch",
            "patchNumber",
            "patch_number",
            "patchProductiveLength",
            "patch_productive_length",
            "defectType",
            "defect_type",
            "defectDescription",
            "defect_description",
            "totalLength",
            "total_length",
            "stockDate",
            "stock_date",
            "remarks",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]
        read_only_fields = [
            "id",
            "clothName",
            "cloth_name",
            "patchNumber",
            "patch_number",
            "patchProductiveLength",
            "patch_productive_length",
            "createdAt",
            "updatedAt",
            "created_at",
            "updated_at",
            "createdBy",
            "updatedBy",
        ]

    def get_clothName(self, obj):
        if obj.cloth_stock:
            return _format_cloth_name_summary(obj.cloth_stock.cloth_name)
        return None

    def get_cloth_name(self, obj):
        return self.get_clothName(obj)

    def get_patchNumber(self, obj):
        return obj.cloth_patch.patch_number if obj.cloth_patch else ""

    def get_patch_number(self, obj):
        return self.get_patchNumber(obj)

    def get_patchProductiveLength(self, obj):
        return str(obj.cloth_patch.productive_length) if obj.cloth_patch else "0.000000"

    def get_patch_productive_length(self, obj):
        return self.get_patchProductiveLength(obj)

    def get_createdBy(self, obj):
        if obj.created_by:
            return {"id": obj.created_by.id, "username": obj.created_by.username}
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {"id": obj.updated_by.id, "username": obj.updated_by.username}
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        mapping = {
            "cloth_stock": "clothStock",
            "cloth_stock_id": "clothStockId",
            "cloth_patch": "clothPatch",
            "cloth_patch_id": "clothPatchId",
            "defect_type": "defectType",
            "defect_description": "defectDescription",
            "total_length": "totalLength",
            "stock_date": "stockDate",
        }
        for snake, camel in mapping.items():
            if snake in data and camel not in data:
                data[camel] = data[snake]
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Resolve clothPatch
        patch = attrs.get("cloth_patch")
        patch_id = (
            self.initial_data.get("cloth_patch")
            or self.initial_data.get("cloth_patch_id")
            or self.initial_data.get("clothPatch")
            or self.initial_data.get("clothPatchId")
        )
        if not patch and patch_id:
            try:
                attrs["cloth_patch"] = ClothPatch.objects.get(id=patch_id)
            except ClothPatch.DoesNotExist:
                raise serializers.ValidationError({"clothPatch": [f"ClothPatch #{patch_id} does not exist."]})
        elif not patch and not self.instance:
            raise serializers.ValidationError({"clothPatch": ["cloth_patch is required."]})

        resolved_patch = attrs.get("cloth_patch") or (self.instance.cloth_patch if self.instance else None)

        # Resolve clothStock
        stock = attrs.get("cloth_stock")
        stock_id = (
            self.initial_data.get("cloth_stock")
            or self.initial_data.get("cloth_stock_id")
            or self.initial_data.get("clothStock")
            or self.initial_data.get("clothStockId")
        )
        if not stock and stock_id:
            try:
                attrs["cloth_stock"] = ClothStock.objects.get(id=stock_id)
            except ClothStock.DoesNotExist:
                raise serializers.ValidationError({"clothStock": [f"ClothStock #{stock_id} does not exist."]})
        elif not stock and not self.instance:
            if resolved_patch and resolved_patch.cloth_name:
                stock_obj, _ = ClothStock.objects.get_or_create(
                    cloth_name=resolved_patch.cloth_name,
                    defaults={"total_length": Decimal("0.000000")}
                )
                attrs["cloth_stock"] = stock_obj
            else:
                raise serializers.ValidationError({"clothStock": ["cloth_stock is required."]})

        resolved_stock = attrs.get("cloth_stock") or (self.instance.cloth_stock if self.instance else None)

        # Validate cloth_name consistency
        if resolved_stock and resolved_patch:
            if resolved_stock.cloth_name_id != resolved_patch.cloth_name_id:
                raise serializers.ValidationError({
                    "clothStock": [
                        f"ClothStock cloth name '{resolved_stock.cloth_name.name}' does not match "
                        f"ClothPatch cloth name '{resolved_patch.cloth_name.name}'."
                    ]
                })

        # Defect type check
        d_type = attrs.get("defect_type")
        if d_type is not None and not str(d_type).strip():
            raise serializers.ValidationError({"defectType": ["Defect type cannot be blank."]})

        # Length validation
        length = attrs.get("total_length")
        if length is not None:
            if length <= Decimal("0.000000"):
                raise serializers.ValidationError({"totalLength": ["Total length must be strictly positive (> 0)."]})
            # Check allocation invariant
            validate_patch_allocation(
                cloth_patch=resolved_patch,
                new_length=length,
                cloth_stock=resolved_stock,
                exclude_defected_id=self.instance.id if self.instance else None,
            )

        return attrs

    def create(self, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        return create_defected_cloth_stock(
            cloth_stock_or_id=validated_data["cloth_stock"],
            cloth_patch_or_id=validated_data["cloth_patch"],
            defect_type=validated_data["defect_type"],
            total_length=validated_data["total_length"],
            stock_date=validated_data["stock_date"],
            defect_description=validated_data.get("defect_description", ""),
            remarks=validated_data.get("remarks", ""),
            user=user,
            request=self.context.get("request"),
        )

    def update(self, instance, validated_data):
        user = self.context["request"].user if "request" in self.context and self.context["request"].user.is_authenticated else None
        return update_defected_cloth_stock(
            defected_stock_or_id=instance,
            defect_type=validated_data.get("defect_type"),
            total_length=validated_data.get("total_length"),
            stock_date=validated_data.get("stock_date"),
            defect_description=validated_data.get("defect_description"),
            remarks=validated_data.get("remarks"),
            user=user,
            request=self.context.get("request"),
        )
