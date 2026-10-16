"""
Django Admin registrations for Cloth models.
"""

from django.contrib import admin
from .models import (
    ClothName,
    ClothPatch,
    ClothStock,
    CleanClothStock,
    DefectedClothStock,
)


@admin.register(ClothName)
class ClothNameAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "warp_count",
        "weft_count",
        "reed_count",
        "pick_count",
        "reed_width",
        "created_at",
        "updated_at",
    ]
    search_fields = ["name", "warp_count", "weft_count"]


@admin.register(ClothPatch)
class ClothPatchAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "patch_number",
        "cloth_name",
        "loom",
        "beam",
        "beam_loading",
        "patch_date",
        "productive_length",
        "bundle_count",
    ]
    search_fields = ["patch_number", "cloth_name__name", "loom__loom_code", "beam__beam_number"]
    list_filter = ["cloth_name", "patch_date", "loom", "beam"]


@admin.register(ClothStock)
class ClothStockAdmin(admin.ModelAdmin):
    list_display = ["id", "cloth_name", "total_length", "updated_at"]
    search_fields = ["cloth_name__name"]


@admin.register(CleanClothStock)
class CleanClothStockAdmin(admin.ModelAdmin):
    list_display = ["id", "cloth_stock", "cloth_patch", "total_length", "stock_date"]
    search_fields = ["cloth_patch__patch_number", "cloth_stock__cloth_name__name"]
    list_filter = ["cloth_stock", "stock_date"]


@admin.register(DefectedClothStock)
class DefectedClothStockAdmin(admin.ModelAdmin):
    list_display = ["id", "cloth_stock", "cloth_patch", "defect_type", "total_length", "stock_date"]
    search_fields = ["defect_type", "cloth_patch__patch_number", "cloth_stock__cloth_name__name"]
    list_filter = ["defect_type", "cloth_stock", "stock_date"]
