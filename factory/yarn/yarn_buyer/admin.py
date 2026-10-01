"""
Admin for the YarnBuyer module.
"""
from django.contrib import admin
from .models import YarnBuyer


@admin.register(YarnBuyer)
class YarnBuyerAdmin(admin.ModelAdmin):
    list_display = ["buyer_name", "company_name", "phone_no", "city", "country", "status", "created_at"]
    list_filter = ["status", "country", "city"]
    search_fields = ["buyer_name", "company_name", "phone_no", "email"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
