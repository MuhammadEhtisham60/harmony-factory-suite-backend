"""
Filters for the YarnIntake module.
"""

import django_filters
from django.db.models import Q
from .models import YarnIntake


class YarnIntakeFilter(django_filters.FilterSet):
    yarn_name = django_filters.CharFilter(field_name="yarn_name__name", lookup_expr="icontains")
    yarn_name_id = django_filters.NumberFilter(field_name="yarn_name__id")
    yarn_type = django_filters.CharFilter(field_name="yarn_type__name", lookup_expr="icontains")
    yarn_type_id = django_filters.NumberFilter(field_name="yarn_type__id")
    yarn_count = django_filters.CharFilter(field_name="yarn_count__name", lookup_expr="icontains")
    yarn_count_id = django_filters.NumberFilter(field_name="yarn_count__id")
    production_type = django_filters.CharFilter(field_name="production_type", lookup_expr="icontains")
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    stock = django_filters.NumberFilter(field_name="stock__id")
    stock_id = django_filters.NumberFilter(field_name="stock__id")
    set_no = django_filters.CharFilter(field_name="set_no", lookup_expr="icontains")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    intake_date_after = django_filters.DateFilter(field_name="intake_date", lookup_expr="gte")
    intake_date_before = django_filters.DateFilter(field_name="intake_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnIntake
        fields = [
            "yarn_name",
            "yarn_name_id",
            "yarn_type",
            "yarn_type_id",
            "yarn_count",
            "yarn_count_id",
            "production_type",
            "supplier",
            "stock",
            "set_no",
        ]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(yarn_name__name__icontains=value)
            | Q(yarn_type__name__icontains=value)
            | Q(yarn_count__name__icontains=value)
            | Q(set_no__icontains=value)
            | Q(production_type__icontains=value)
            | Q(supplier__supplier_name__icontains=value)
        )

    def filter_in_stock(self, queryset, name, value):  # noqa: ARG002
        if value:
            return queryset.filter(remaining_bags__gt=0)
        return queryset
