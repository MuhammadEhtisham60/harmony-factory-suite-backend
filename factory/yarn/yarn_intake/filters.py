"""
Filters for the YarnIntake module.
"""

import django_filters
from django.db.models import Q
from .models import YarnIntake


class YarnIntakeFilter(django_filters.FilterSet):
    yarn_type = django_filters.CharFilter(field_name="yarn_type", lookup_expr="icontains")
    yarn_count = django_filters.CharFilter(field_name="yarn_count", lookup_expr="icontains")
    production_type = django_filters.CharFilter(field_name="production_type", lookup_expr="icontains")
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    intake_date_after = django_filters.DateFilter(field_name="intake_date", lookup_expr="gte")
    intake_date_before = django_filters.DateFilter(field_name="intake_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnIntake
        fields = ["yarn_type", "yarn_count", "production_type", "supplier"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(yarn_name__icontains=value)
            | Q(yarn_type__icontains=value)
            | Q(yarn_count__icontains=value)
            | Q(set_no__icontains=value)
            | Q(production_type__icontains=value)
            | Q(supplier__supplier_name__icontains=value)
        )
