"""
Filters for Cloth Production and Inventory.
"""

from django_filters import rest_framework as filters
from .models import (
    ClothName,
    ClothPatch,
    ClothStock,
    CleanClothStock,
    DefectedClothStock,
)


class ClothPatchFilter(filters.FilterSet):
    patch_number = filters.CharFilter(lookup_expr="icontains")
    patchNumber = filters.CharFilter(field_name="patch_number", lookup_expr="icontains")

    set_no = filters.CharFilter(lookup_expr="icontains")
    setNo = filters.CharFilter(field_name="set_no", lookup_expr="icontains")

    cloth_name = filters.ModelChoiceFilter(queryset=ClothName.objects.all())
    cloth_name_id = filters.NumberFilter(field_name="cloth_name_id")
    clothNameId = filters.NumberFilter(field_name="cloth_name_id")
    cloth_name_title = filters.CharFilter(field_name="cloth_name__name", lookup_expr="icontains")

    loom = filters.NumberFilter(field_name="loom_id")
    loom_id = filters.NumberFilter(field_name="loom_id")
    loomId = filters.NumberFilter(field_name="loom_id")

    beam = filters.NumberFilter(field_name="beam_id")
    beam_id = filters.NumberFilter(field_name="beam_id")
    beamId = filters.NumberFilter(field_name="beam_id")

    beam_loading = filters.NumberFilter(field_name="beam_loading_id")
    beam_loading_id = filters.NumberFilter(field_name="beam_loading_id")
    beamLoadingId = filters.NumberFilter(field_name="beam_loading_id")

    patch_date = filters.DateFilter()
    patchDate = filters.DateFilter(field_name="patch_date")
    date_from = filters.DateFilter(field_name="patch_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="patch_date", lookup_expr="lte")

    class Meta:
        model = ClothPatch
        fields = [
            "patch_number",
            "set_no",
            "cloth_name",
            "cloth_name_id",
            "loom",
            "loom_id",
            "beam",
            "beam_id",
            "beam_loading",
            "beam_loading_id",
            "patch_date",
        ]


class ClothStockFilter(filters.FilterSet):
    cloth_name = filters.NumberFilter(field_name="cloth_name_id")
    clothName = filters.NumberFilter(field_name="cloth_name_id")
    cloth_name_id = filters.NumberFilter(field_name="cloth_name_id")
    clothNameId = filters.NumberFilter(field_name="cloth_name_id")
    name = filters.CharFilter(field_name="cloth_name__name", lookup_expr="icontains")

    class Meta:
        model = ClothStock
        fields = ["cloth_name", "cloth_name_id", "name"]


class CleanClothStockFilter(filters.FilterSet):
    cloth_stock = filters.NumberFilter(field_name="cloth_stock_id")
    clothStock = filters.NumberFilter(field_name="cloth_stock_id")
    cloth_stock_id = filters.NumberFilter(field_name="cloth_stock_id")
    clothStockId = filters.NumberFilter(field_name="cloth_stock_id")

    cloth_patch = filters.NumberFilter(field_name="cloth_patch_id")
    clothPatch = filters.NumberFilter(field_name="cloth_patch_id")
    cloth_patch_id = filters.NumberFilter(field_name="cloth_patch_id")
    clothPatchId = filters.NumberFilter(field_name="cloth_patch_id")

    patch_number = filters.CharFilter(field_name="cloth_patch__patch_number", lookup_expr="icontains")
    patchNumber = filters.CharFilter(field_name="cloth_patch__patch_number", lookup_expr="icontains")

    stock_date = filters.DateFilter()
    stockDate = filters.DateFilter(field_name="stock_date")
    date_from = filters.DateFilter(field_name="stock_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="stock_date", lookup_expr="lte")

    class Meta:
        model = CleanClothStock
        fields = ["cloth_stock", "cloth_stock_id", "cloth_patch", "cloth_patch_id", "stock_date"]


class DefectedClothStockFilter(filters.FilterSet):
    cloth_stock = filters.NumberFilter(field_name="cloth_stock_id")
    clothStock = filters.NumberFilter(field_name="cloth_stock_id")
    cloth_stock_id = filters.NumberFilter(field_name="cloth_stock_id")
    clothStockId = filters.NumberFilter(field_name="cloth_stock_id")

    cloth_patch = filters.NumberFilter(field_name="cloth_patch_id")
    clothPatch = filters.NumberFilter(field_name="cloth_patch_id")
    cloth_patch_id = filters.NumberFilter(field_name="cloth_patch_id")
    clothPatchId = filters.NumberFilter(field_name="cloth_patch_id")

    defect_type = filters.CharFilter(lookup_expr="icontains")
    defectType = filters.CharFilter(field_name="defect_type", lookup_expr="icontains")

    patch_number = filters.CharFilter(field_name="cloth_patch__patch_number", lookup_expr="icontains")
    patchNumber = filters.CharFilter(field_name="cloth_patch__patch_number", lookup_expr="icontains")

    stock_date = filters.DateFilter()
    stockDate = filters.DateFilter(field_name="stock_date")
    date_from = filters.DateFilter(field_name="stock_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="stock_date", lookup_expr="lte")

    class Meta:
        model = DefectedClothStock
        fields = [
            "cloth_stock",
            "cloth_stock_id",
            "cloth_patch",
            "cloth_patch_id",
            "defect_type",
            "stock_date",
        ]
