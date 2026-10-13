"""
Admin registration for YarnCount.
"""

from django.contrib import admin
from .models import YarnCount


@admin.register(YarnCount)
class YarnCountAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
