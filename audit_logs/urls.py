"""
URLs for audit_logs module (Activity Logs).
"""

from django.urls import path
from .views import ActivityLogListView

urlpatterns = [
    path('activities/', ActivityLogListView.as_view(), name='activities-list'),
]
