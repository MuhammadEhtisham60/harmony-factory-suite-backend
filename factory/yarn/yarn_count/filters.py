"""
Filters for the YarnCount model.
"""

import django_filters
from django.db.models import Q
from .models import YarnCount


class YarnCountFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnCount
        fields = ["name", "status"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )
