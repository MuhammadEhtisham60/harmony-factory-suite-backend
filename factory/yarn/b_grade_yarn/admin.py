"""
Django Admin registration for BGradeYarn.
"""

from django.contrib import admin
from .models import BGradeYarn


@admin.register(BGradeYarn)
class BGradeYarnAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "yarn_name",
        "yarn_count",
        "yarn_type",
        "production_type",
        "cones",
        "weight_kg",
        "weight_lb",
        "lot_number",
        "entry_date",
        "created_at",
    ]
    list_filter = [
        "production_type",
        "yarn_name",
        "yarn_type",
        "yarn_count",
        "entry_date",
    ]
    search_fields = [
        "yarn_name__name",
        "yarn_type__name",
        "yarn_count__name",
        "lot_number",
        "remarks",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
