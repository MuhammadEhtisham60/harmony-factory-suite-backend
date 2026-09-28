"""
Serializers for Audit & Activity Logs module.
"""

from rest_framework import serializers
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    userId = serializers.SerializerMethodField()
    userFullName = serializers.CharField(source='user_full_name')
    ipAddress = serializers.CharField(source='ip_address')

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'timestamp',
            'date',
            'userId',
            'username',
            'userFullName',
            'action',
            'description',
            'module',
            'ipAddress',
            'device',
            'status',
        ]

    def get_timestamp(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d %b %Y, %I:%M %p')
        return None

    def get_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%Y-%m-%d')
        return None

    def get_userId(self, obj):
        if obj.user:
            return obj.user.formatted_id
        return None
