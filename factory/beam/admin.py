"""
Admin registration for the Beam module.
"""

from django.contrib import admin
from .models import Beam, BeamLoading, Production


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


@admin.register(BeamLoading)
class BeamLoadingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "beam",
        "loom",
        "sizing_outcome",
        "status",
        "warp_count",
        "weft_count",
        "reed_width",
        "pick",
        "installation_date",
        "created_at",
    ]
    list_filter = ["status", "installation_date"]
    search_fields = [
        "beam__beam_code",
        "beam__beam_number",
        "loom__loom_code",
        "sizing_outcome__set_no",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["-installation_date", "-id"]


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "beam_loading",
        "beam",
        "loom",
        "production_date",
        "shift",
        "meters_produced",
        "operator_name",
        "beam_emptied",
        "created_at",
    ]
    list_filter = ["production_date", "shift", "beam_emptied"]
    search_fields = [
        "operator_name",
        "beam__beam_code",
        "loom__loom_code",
        "remarks",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["-production_date", "-id"]

