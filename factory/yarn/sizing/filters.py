"""
Filters for the Sizing module.
"""

import django_filters
from django.db.models import Q
from .models import Sizing


class SizingFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Sizing.StatusChoices.choices)
    search = django_filters.CharFilter(method="filter_search", label="Search")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Sizing
        fields = ["status"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(sizing_name__icontains=value)
            | Q(contact_person__icontains=value)
            | Q(phone_no__icontains=value)
            | Q(email__icontains=value)
            | Q(address__icontains=value)
        )
