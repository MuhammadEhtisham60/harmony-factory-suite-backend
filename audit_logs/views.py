"""
Views for Activity & Audit Logs module.
"""

from datetime import datetime
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import ActivityLog
from .serializers import ActivityLogSerializer
from accounts.permissions import require_permission
from accounts.pagination import ActivityLogPagination


class ActivityLogListView(APIView):
    """
    GET /api/v1/activities/
    Lists system activity and audit trail logs with filtering, searching, and pagination.
    """
    permission_classes = [IsAuthenticated, require_permission('activity.view')]
    pagination_class = ActivityLogPagination

    def get(self, request):
        queryset = ActivityLog.objects.select_related('user').all()

        # Keyword search
        search_query = request.query_params.get('search')
        if search_query:
            search_query = search_query.strip()
            queryset = queryset.filter(
                Q(description__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(user_full_name__icontains=search_query) |
                Q(ip_address__icontains=search_query) |
                Q(module__icontains=search_query)
            )

        # Action filter
        action = request.query_params.get('action')
        if action:
            queryset = queryset.filter(action__iexact=action.strip())

        # Username filter
        username = request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__iexact=username.strip())

        # Module filter
        module = request.query_params.get('module')
        if module:
            queryset = queryset.filter(module__iexact=module.strip())

        # Status filter
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status__iexact=status_param.strip())

        # Date range filter
        date_from = request.query_params.get('date_from')
        if date_from:
            try:
                from_dt = datetime.strptime(date_from.strip(), '%Y-%m-%d')
                queryset = queryset.filter(created_at__date__gte=from_dt.date())
            except ValueError:
                pass

        date_to = request.query_params.get('date_to')
        if date_to:
            try:
                to_dt = datetime.strptime(date_to.strip(), '%Y-%m-%d')
                queryset = queryset.filter(created_at__date__lte=to_dt.date())
            except ValueError:
                pass

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ActivityLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
