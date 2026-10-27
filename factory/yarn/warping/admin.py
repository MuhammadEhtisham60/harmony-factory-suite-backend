"""
Admin for the Warping master.
"""
from django.contrib import admin
from .models import Warping


@admin.register(Warping)
class WarpingAdmin(admin.ModelAdmin):
    list_display = ["warping_name", "contact_person", "phone_no", "email", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["warping_name", "contact_person", "phone_no", "email"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["warping_name"]

    fieldsets = (
        ("Identification", {"fields": ("warping_name", "status")}),
        ("Contact", {"fields": ("contact_person", "phone_no", "email", "address")}),
        ("Notes", {"fields": ("notes",)}),
        ("Audit", {
            "fields": ("created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
