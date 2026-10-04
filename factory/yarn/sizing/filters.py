"""
Filters for Sizing, SizingOutcome, and SizingBeamAssignment modules.
"""

import django_filters
from django.db.models import Q
from .models import Sizing, SizingOutcome, SizingBeamAssignment


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


class SizingOutcomeFilter(django_filters.FilterSet):
    sizing = django_filters.NumberFilter(field_name="sizing_id")
    outcome_date = django_filters.DateFilter(field_name="outcome_date")
    start_date = django_filters.DateFilter(field_name="outcome_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="outcome_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = SizingOutcome
        fields = ["sizing", "outcome_date"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(sizing__sizing_name__icontains=value)
            | Q(sizing__contact_person__icontains=value)
            | Q(remarks__icontains=value)
        )


class SizingBeamAssignmentFilter(django_filters.FilterSet):
    beam = django_filters.NumberFilter(field_name="beam")
    yarn_outcome = django_filters.NumberFilter(field_name="yarn_outcome_id")
    sizing_outcome = django_filters.NumberFilter(field_name="yarn_outcome_id")
    status = django_filters.ChoiceFilter(choices=SizingBeamAssignment.StatusChoices.choices)
    is_active = django_filters.BooleanFilter(method="filter_is_active", label="Is Active")

    class Meta:
        model = SizingBeamAssignment
        fields = ["beam", "yarn_outcome", "sizing_outcome", "status"]

    def filter_is_active(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                status__in=[
                    SizingBeamAssignment.StatusChoices.ASSIGNED,
                    SizingBeamAssignment.StatusChoices.IN_USE,
                ]
            )
        elif value is False:
            return queryset.filter(
                status__in=[
                    SizingBeamAssignment.StatusChoices.COMPLETED,
                    SizingBeamAssignment.StatusChoices.RELEASED,
                ]
            )
        return queryset
