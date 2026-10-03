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
        "status",
        "location",
        "installation_date",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = [
        "loom_code",
        "loom_name",
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
                    "status",
                )
            },
        ),
        (
            "Technical Details",
            {
                "fields": (
                    "model_number",
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
