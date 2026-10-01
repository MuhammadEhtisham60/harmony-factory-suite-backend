"""
Filters for the YarnBuyer module.
"""

import django_filters
from django.db.models import Q
from .models import YarnBuyer


class YarnBuyerFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    country = django_filters.CharFilter(field_name="country", lookup_expr="icontains")
    search = django_filters.CharFilter(method="filter_search", label="Search")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = YarnBuyer
        fields = ["status", "city", "country"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(buyer_name__icontains=value)
            | Q(company_name__icontains=value)
            | Q(phone_no__icontains=value)
            | Q(email__icontains=value)
            | Q(city__icontains=value)
        )
