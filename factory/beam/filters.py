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


class BeamLoadingFilter(django_filters.FilterSet):
    """
    FilterSet for BeamLoading.
    Supported query params:
        sizing_outcome     – exact integer ID
        beam               – exact integer ID
        loom               – exact integer ID
        status             – exact status (Loaded / In Production / Completed / Cancelled)
        search             – free-text across beam_code, beam_number, loom_code, set_no
        installation_after – YYYY-MM-DD, installed on or after
        installation_before– YYYY-MM-DD, installed on or before
    """
    from .models import BeamLoading

    sizing_outcome = django_filters.NumberFilter(field_name="sizing_outcome_id")
    beam = django_filters.NumberFilter(field_name="beam_id")
    loom = django_filters.NumberFilter(field_name="loom_id")
    status = django_filters.ChoiceFilter(choices=BeamLoading.StatusChoices.choices)

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search"
    )

    installation_after = django_filters.DateFilter(
        field_name="installation_date",
        lookup_expr="gte"
    )

    installation_before = django_filters.DateFilter(
        field_name="installation_date",
        lookup_expr="lte"
    )

    class Meta:
        from .models import BeamLoading
        model = BeamLoading
        fields = ["sizing_outcome", "beam", "loom", "status"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(beam__beam_code__icontains=value)
            | Q(beam__beam_number__icontains=value)
            | Q(loom__loom_code__icontains=value)
            | Q(sizing_outcome__set_no__icontains=value)
            | Q(warp_count__icontains=value)
            | Q(weft_count__icontains=value)
        )


class ProductionFilter(django_filters.FilterSet):
    """
    FilterSet for Production.
    Supported query params:
        beam_loading       – exact integer ID
        beam               – exact integer ID
        loom               – exact integer ID
        production_date    – exact YYYY-MM-DD
        date_after         – YYYY-MM-DD, produced on or after
        date_before        – YYYY-MM-DD, produced on or before
        shift              – exact or icontains
        beam_emptied       – boolean (true/false)
        search             – free-text across operator_name, beam_code, loom_code
    """
    beam_loading = django_filters.NumberFilter(field_name="beam_loading_id")
    beam = django_filters.NumberFilter(field_name="beam_id")
    loom = django_filters.NumberFilter(field_name="loom_id")
    production_date = django_filters.DateFilter(field_name="production_date")
    date_after = django_filters.DateFilter(field_name="production_date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="production_date", lookup_expr="lte")
    shift = django_filters.CharFilter(field_name="shift", lookup_expr="icontains")
    beam_emptied = django_filters.BooleanFilter(field_name="beam_emptied")

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search"
    )

    class Meta:
        from .models import Production
        model = Production
        fields = ["beam_loading", "beam", "loom", "production_date", "shift", "beam_emptied"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(operator_name__icontains=value)
            | Q(beam__beam_code__icontains=value)
            | Q(loom__loom_code__icontains=value)
            | Q(remarks__icontains=value)
        )

