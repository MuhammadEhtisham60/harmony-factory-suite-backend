"""
FilterSet for the Loom module.
"""

import django_filters
from django.db.models import Q
from .models import Loom


class LoomFilter(django_filters.FilterSet):
    """
    Supported query params:
        status              – exact  (Active / Inactive / Sizing / Production / Maintenance / Breakdown)
        location            – icontains free-text
        search              – icontains across loom_code, loom_name, model_number, location
        installed_after     – YYYY-MM-DD, installation_date on or after
        installed_before    – YYYY-MM-DD, installation_date on or before
        created_after       – YYYY-MM-DD, record created on or after
        created_before      – YYYY-MM-DD, record created on or before
    """

    status = django_filters.ChoiceFilter(
        choices=Loom.StatusChoices.choices
    )

    location = django_filters.CharFilter(
        field_name="location",
        lookup_expr="icontains"
    )

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search"
    )

    installed_after = django_filters.DateFilter(
        field_name="installation_date",
        lookup_expr="gte"
    )

    installed_before = django_filters.DateFilter(
        field_name="installation_date",
        lookup_expr="lte"
    )

    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte"
    )

    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte"
    )

    class Meta:
        model = Loom
        fields = ["status", "location"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(loom_code__icontains=value)
            | Q(loom_name__icontains=value)
            | Q(location__icontains=value)
            | Q(model_number__icontains=value)
        )
