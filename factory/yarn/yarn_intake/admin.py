"""
Admin for the YarnIntake module.
"""
from django.contrib import admin
from .models import YarnIntake, YarnOutcome, YarnOutcomeItem


class YarnOutcomeItemInline(admin.TabularInline):
    model = YarnOutcomeItem
    extra = 0
    fields = ["yarn_intake", "bags", "cones_per_bag", "weight_per_bag_kg", "weight_kg", "weight_lb"]
    readonly_fields = ["weight_kg", "weight_lb"]


@admin.register(YarnIntake)
class YarnIntakeAdmin(admin.ModelAdmin):
    list_display = [
        "yarn_name", "set_no", "yarn_type", "yarn_count",
        "bags", "remaining_bags", "status_display", "intake_date",
    ]
    list_filter = ["yarn_type", "intake_date"]
    search_fields = ["yarn_name__name", "set_no", "yarn_type__name", "yarn_count__name"]
    readonly_fields = [
        "total_cones", "total_rate", "net_weight_kg", "net_weight_lb",
        "outcome_bags", "outcome_weight_kg", "outcome_weight_lb",
        "return_bags", "return_cones",
        "remaining_bags", "remaining_cones", "remaining_weight_kg", "remaining_weight_lb",
        "created_at", "updated_at", "created_by", "updated_by",
    ]
    inlines = [YarnOutcomeItemInline]

    def status_display(self, obj):
        pct = 0
        if obj.bags > 0:
            pct = round((obj.remaining_bags / obj.bags) * 100)
        return f"{obj.remaining_bags}/{obj.bags} bags ({pct}% left)"
    status_display.short_description = "Stock"


@admin.register(YarnOutcome)
class YarnOutcomeAdmin(admin.ModelAdmin):
    list_display = [
        "id", "primary_intake", "outcome_type", "outcome_bags",
        "outcome_weight_kg", "yarn_buyer", "total_price", "outcome_date",
    ]
    list_filter = ["outcome_type", "outcome_date"]
    search_fields = ["items__yarn_intake__yarn_name__name", "items__yarn_intake__set_no", "yarn_buyer__buyer_name"]
    readonly_fields = ["outcome_weight_kg", "outcome_weight_lb", "created_at", "updated_at"]
    inlines = [YarnOutcomeItemInline]


@admin.register(YarnOutcomeItem)
class YarnOutcomeItemAdmin(admin.ModelAdmin):
    list_display = ["yarn_outcome", "yarn_intake", "bags", "weight_kg", "weight_lb", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["yarn_outcome__id", "yarn_intake__set_no"]
    readonly_fields = ["weight_kg", "weight_lb", "created_at", "updated_at"]
