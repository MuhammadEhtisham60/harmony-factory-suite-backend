"""
Admin for the YarnIntake module.
"""
from django.contrib import admin
from .models import YarnIntake, YarnOutcome


class YarnOutcomeInline(admin.TabularInline):
    model = YarnOutcome
    extra = 0
    readonly_fields = ["outcome_weight_kg", "outcome_weight_lb", "created_at", "updated_at"]
    fields = [
        "outcome_type", "outcome_bags", "outcome_cones_per_bag",
        "outcome_weight_per_bag_kg", "outcome_weight_kg", "outcome_weight_lb",
        "yarn_buyer", "total_price", "outcome_date", "notes",
    ]


@admin.register(YarnIntake)
class YarnIntakeAdmin(admin.ModelAdmin):
    list_display = [
        "yarn_name", "set_no", "yarn_type", "yarn_count",
        "bags", "remaining_bags", "status_display", "intake_date",
    ]
    list_filter = ["yarn_type", "intake_date"]
    search_fields = ["yarn_name", "set_no", "yarn_type", "yarn_count"]
    readonly_fields = [
        "total_cones", "total_rate", "net_weight_kg", "net_weight_lb",
        "outcome_bags", "outcome_weight_kg", "outcome_weight_lb",
        "remaining_bags", "remaining_weight_kg", "remaining_weight_lb",
        "created_at", "updated_at", "created_by", "updated_by",
    ]
    inlines = [YarnOutcomeInline]

    def status_display(self, obj):
        pct = 0
        if obj.bags > 0:
            pct = round((obj.remaining_bags / obj.bags) * 100)
        return f"{obj.remaining_bags}/{obj.bags} bags ({pct}% left)"
    status_display.short_description = "Stock"


@admin.register(YarnOutcome)
class YarnOutcomeAdmin(admin.ModelAdmin):
    list_display = [
        "yarn_intake", "outcome_type", "outcome_bags",
        "outcome_weight_kg", "yarn_buyer", "total_price", "outcome_date",
    ]
    list_filter = ["outcome_type", "outcome_date"]
    search_fields = ["yarn_intake__yarn_name", "yarn_intake__set_no", "yarn_buyer__buyer_name"]
    readonly_fields = ["outcome_weight_kg", "outcome_weight_lb", "created_at", "updated_at"]
