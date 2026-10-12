"""
Filters for the YarnOutcome module.
"""

import django_filters
from django.db.models import Q
from factory.yarn.yarn_intake.models import YarnOutcome


class YarnOutcomeFilter(django_filters.FilterSet):
    stock = django_filters.NumberFilter(field_name="stock__id")
    stock_id = django_filters.NumberFilter(field_name="stock__id")
    yarn_intake = django_filters.NumberFilter(field_name="yarn_intake__id")
    yarn_intake_id = django_filters.NumberFilter(field_name="yarn_intake__id")
    outcome_type = django_filters.ChoiceFilter(choices=YarnOutcome.OutcomeTypeChoices.choices)
    yarn_buyer = django_filters.NumberFilter(field_name="yarn_buyer__id")
    yarn_name = django_filters.CharFilter(method="filter_yarn_name")
    yarn_type = django_filters.CharFilter(method="filter_yarn_type")
    yarn_count = django_filters.CharFilter(method="filter_yarn_count")
    production_type = django_filters.CharFilter(method="filter_production_type")

    outcome_date_after = django_filters.DateFilter(field_name="outcome_date", lookup_expr="gte")
    outcome_date_before = django_filters.DateFilter(field_name="outcome_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = YarnOutcome
        fields = [
            "stock",
            "yarn_intake",
            "outcome_type",
            "yarn_buyer",
            "yarn_name",
            "yarn_type",
            "yarn_count",
            "production_type",
        ]

    def filter_yarn_name(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(Q(stock__yarn_name__icontains=value) | Q(yarn_intake__yarn_name__icontains=value))

    def filter_yarn_type(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(Q(stock__yarn_type__icontains=value) | Q(yarn_intake__yarn_type__icontains=value))

    def filter_yarn_count(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(Q(stock__yarn_count__icontains=value) | Q(yarn_intake__yarn_count__icontains=value))

    def filter_production_type(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(Q(stock__production_type__icontains=value) | Q(yarn_intake__production_type__icontains=value))

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(stock__yarn_name__icontains=value)
            | Q(stock__yarn_count__icontains=value)
            | Q(stock__yarn_type__icontains=value)
            | Q(yarn_intake__yarn_name__icontains=value)
            | Q(yarn_intake__set_no__icontains=value)
            | Q(outcome_type__icontains=value)
            | Q(yarn_buyer__buyer_name__icontains=value)
        )
