"""
FilterSet for the Beam module.
"""

import django_filters
from django.db.models import Q
from .models import Beam


class BeamFilter(django_filters.FilterSet):
    """
    Supported query params:
        status              – exact  (Available / Sizing / Loaded / In Production / Completed / Damaged / Inactive)
        production_order    – icontains free-text
        yarn_count          – icontains free-text
        search              – icontains across beam_code, beam_name, beam_number, yarn_count, production_order
        created_after       – YYYY-MM-DD, record created on or after
        created_before      – YYYY-MM-DD, record created on or before
        min_length          – decimal, filter beams with length >= value
        max_length          – decimal, filter beams with length <= value
        min_weight          – decimal, filter beams with weight >= value
        max_weight          – decimal, filter beams with weight <= value
    """

    status = django_filters.ChoiceFilter(
        choices=Beam.StatusChoices.choices
    )

    production_order = django_filters.CharFilter(
        field_name="production_order",
        lookup_expr="icontains"
    )

    yarn_count = django_filters.CharFilter(
        field_name="yarn_count",
        lookup_expr="icontains"
    )

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search"
    )

    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte"
    )

    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte"
    )

    # Numeric range filters
    min_length = django_filters.NumberFilter(
        field_name="length",
        lookup_expr="gte"
    )

    max_length = django_filters.NumberFilter(
        field_name="length",
        lookup_expr="lte"
    )

    min_weight = django_filters.NumberFilter(
        field_name="weight",
        lookup_expr="gte"
    )

    max_weight = django_filters.NumberFilter(
        field_name="weight",
        lookup_expr="lte"
    )

    class Meta:
        model = Beam
        fields = ["status", "production_order", "yarn_count"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(beam_code__icontains=value)
            | Q(beam_name__icontains=value)
            | Q(beam_number__icontains=value)
            | Q(yarn_count__icontains=value)
            | Q(production_order__icontains=value)
        )
