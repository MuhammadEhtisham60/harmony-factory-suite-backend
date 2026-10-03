"""
Admin for Sizing, SizingOutcome, and SizingBeamAssignment.
"""
from django.contrib import admin
from .models import Sizing, SizingOutcome, SizingBeamAssignment


class SizingBeamAssignmentInline(admin.TabularInline):
    model = SizingBeamAssignment
    extra = 0
    fields = ["beam", "status", "assigned_at", "released_at"]
    readonly_fields = ["assigned_at"]


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


@admin.register(SizingOutcome)
class SizingOutcomeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "set_no",
        "sizing_name",
        "sizing",
        "outcome_date",
        "total_bags_on_sizing",
        "total_cones",
        "lagat_bags",
        "lagat_cones",
        "total_beams",
        "created_at",
    ]
    list_filter = ["outcome_date", "sizing"]
    search_fields = ["set_no", "sizing_name", "sizing__sizing_name", "remarks"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
    inlines = [SizingBeamAssignmentInline]



@admin.register(SizingBeamAssignment)
class SizingBeamAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "beam", "sizing_outcome", "status", "assigned_at", "released_at"]
    list_filter = ["status", "assigned_at"]
    search_fields = ["beam__beam_number", "sizing_outcome__sizing__sizing_name"]
    readonly_fields = ["assigned_at", "created_at", "updated_at", "created_by", "updated_by"]
