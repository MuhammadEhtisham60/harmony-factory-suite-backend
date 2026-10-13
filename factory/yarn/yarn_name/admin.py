"""
Admin registration for YarnName.
"""

from django.contrib import admin
from .models import YarnName


@admin.register(YarnName)
class YarnNameAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at", "created_by", "updated_by"]
