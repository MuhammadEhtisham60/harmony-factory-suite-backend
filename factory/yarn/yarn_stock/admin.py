"""
Django admin configuration for YarnStock.
"""

from django.contrib import admin
from .models import YarnStock


@admin.register(YarnStock)
class YarnStockAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "yarn_name",
        "yarn_type",
        "yarn_count",
        "production_type",
        "total_boxes",
        "cones",
        "total_weight_kg",
        "total_weight_lb",
        "price",
        "created_at",
        "updated_at",
    ]
    list_filter = ["yarn_type", "production_type", "created_at"]
    search_fields = ["yarn_name__name", "yarn_type__name", "yarn_count__name", "production_type"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
