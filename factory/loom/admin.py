"""
Admin registration for the Loom module.
"""

from django.contrib import admin
from .models import Loom


@admin.register(Loom)
class LoomAdmin(admin.ModelAdmin):
    list_display = [
        "loom_code",
        "loom_name",
        "loom_type",
        "manufacturer",
        "status",
        "location",
        "installation_date",
        "created_at",
    ]
    list_filter = ["status", "loom_type", "manufacturer"]
    search_fields = [
        "loom_code",
        "loom_name",
        "loom_type",
        "manufacturer",
        "serial_number",
        "model_number",
        "location",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["loom_code"]

    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "loom_code",
                    "loom_name",
                    "loom_type",
                    "status",
                )
            },
        ),
        (
            "Technical Details",
            {
                "fields": (
                    "manufacturer",
                    "model_number",
                    "serial_number",
                    "width",
                    "installation_date",
                )
            },
        ),
        (
            "Location & Notes",
            {
                "fields": (
                    "location",
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
