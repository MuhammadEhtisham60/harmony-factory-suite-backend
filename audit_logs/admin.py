from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_full_name', 'action', 'module', 'status', 'ip_address', 'created_at')
    list_filter = ('action', 'module', 'status', 'created_at')
    search_fields = ('username', 'user_full_name', 'description', 'ip_address')
    readonly_fields = ('created_at',)
