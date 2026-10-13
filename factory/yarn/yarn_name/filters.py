"""
Filters for the YarnName model.
"""

import django_filters
from django.db.models import Q
from .models import YarnName


class YarnNameFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnName
        fields = ["name", "status"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )
