"""
Admin registration for YarnType.
"""

from django.contrib import admin
from .models import YarnType


@admin.register(YarnType)
class YarnTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
