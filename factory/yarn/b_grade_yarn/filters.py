"""
Filters for B-Grade Yarn.
"""

import django_filters
from django.db import models
from .models import BGradeYarn


class BGradeYarnFilter(django_filters.FilterSet):
    yarn_name = django_filters.CharFilter(method="filter_yarn_name")
    yarn_type = django_filters.CharFilter(method="filter_yarn_type")
    yarn_count = django_filters.CharFilter(method="filter_yarn_count")
    production_type = django_filters.CharFilter(field_name="production_type", lookup_expr="iexact")
    lot_number = django_filters.CharFilter(field_name="lot_number", lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="entry_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="entry_date", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = BGradeYarn
        fields = [
            "yarn_name",
            "yarn_type",
            "yarn_count",
            "production_type",
            "lot_number",
            "date_from",
            "date_to",
            "in_stock",
        ]

    def filter_yarn_name(self, queryset, name, value):
        if not value or str(value).lower() in ("all", "none", ""):
            return queryset
        if str(value).isdigit():
            return queryset.filter(models.Q(yarn_name_id=int(value)) | models.Q(yarn_name__name__icontains=value))
        return queryset.filter(yarn_name__name__icontains=value)

    def filter_yarn_type(self, queryset, name, value):
        if not value or str(value).lower() in ("all", "none", ""):
            return queryset
        if str(value).isdigit():
            return queryset.filter(models.Q(yarn_type_id=int(value)) | models.Q(yarn_type__name__icontains=value))
        return queryset.filter(yarn_type__name__icontains=value)

    def filter_yarn_count(self, queryset, name, value):
        if not value or str(value).lower() in ("all", "none", ""):
            return queryset
        if str(value).isdigit():
            return queryset.filter(models.Q(yarn_count_id=int(value)) | models.Q(yarn_count__name__icontains=value))
        return queryset.filter(yarn_count__name__icontains=value)

    def filter_in_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(models.Q(weight_kg__gt=0) | models.Q(cones__gt=0))
        elif value is False:
            return queryset.filter(weight_kg__lte=0, cones__lte=0)
        return queryset
