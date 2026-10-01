"""
Admin for the Sizing module.
"""
from django.contrib import admin
from .models import Sizing


@admin.register(Sizing)
class SizingAdmin(admin.ModelAdmin):
    list_display = ["sizing_name", "contact_person", "phone_no", "email", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["sizing_name", "contact_person", "phone_no", "email"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["sizing_name"]

    fieldsets = (
        ("Identification", {"fields": ("sizing_name", "status")}),
        ("Contact", {"fields": ("contact_person", "phone_no", "email", "address")}),
        ("Notes", {"fields": ("notes",)}),
        ("Audit", {
            "fields": ("created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
