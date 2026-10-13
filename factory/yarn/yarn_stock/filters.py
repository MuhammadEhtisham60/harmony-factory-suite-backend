"""
Filters for the YarnStock module.
"""

import django_filters
from django.db.models import Q
from .models import YarnStock


class YarnStockFilter(django_filters.FilterSet):
    yarn_name = django_filters.CharFilter(field_name="yarn_name__name", lookup_expr="icontains")
    yarn_name_id = django_filters.NumberFilter(field_name="yarn_name__id")
    yarn_type = django_filters.CharFilter(field_name="yarn_type__name", lookup_expr="icontains")
    yarn_type_id = django_filters.NumberFilter(field_name="yarn_type__id")
    yarn_count = django_filters.CharFilter(field_name="yarn_count__name", lookup_expr="icontains")
    yarn_count_id = django_filters.NumberFilter(field_name="yarn_count__id")
    production_type = django_filters.CharFilter(field_name="production_type", lookup_expr="icontains")

    min_boxes = django_filters.NumberFilter(field_name="total_boxes", lookup_expr="gte")
    min_weight_kg = django_filters.NumberFilter(field_name="total_weight_kg", lookup_expr="gte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnStock
        fields = [
            "yarn_name",
            "yarn_name_id",
            "yarn_type",
            "yarn_type_id",
            "yarn_count",
            "yarn_count_id",
            "production_type",
            "min_boxes",
            "min_weight_kg",
            "in_stock",
        ]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        if not value:
            return queryset
        return queryset.filter(
            Q(yarn_name__name__icontains=value)
            | Q(yarn_type__name__icontains=value)
            | Q(yarn_count__name__icontains=value)
            | Q(production_type__icontains=value)
        )

    def filter_in_stock(self, queryset, name, value):  # noqa: ARG002
        if value is True:
            return queryset.filter(Q(total_boxes__gt=0) | Q(total_weight_kg__gt=0))
        elif value is False:
            return queryset.filter(total_boxes__lte=0, total_weight_kg__lte=0)
        return queryset
