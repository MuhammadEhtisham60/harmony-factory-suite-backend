"""
Admin registration for the Beam module.
"""

from django.contrib import admin
from .models import Beam


@admin.register(Beam)
class BeamAdmin(admin.ModelAdmin):
    list_display = [
        "beam_code",
        "beam_number",
        "beam_name",
        "yarn_count",
        "warp_count",
        "total_ends",
        "length",
        "weight",
        "status",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = [
        "beam_code",
        "beam_name",
        "beam_number",
        "yarn_count",
        "production_order",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["beam_code"]

    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "beam_code",
                    "beam_name",
                    "beam_number",
                    "status",
                )
            },
        ),
        (
            "Technical Specifications",
            {
                "fields": (
                    "yarn_count",
                    "warp_count",
                    "total_ends",
                    "length",
                    "weight",
                )
            },
        ),
        (
            "Production",
            {
                "fields": (
                    "production_order",
                    "notes",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )
