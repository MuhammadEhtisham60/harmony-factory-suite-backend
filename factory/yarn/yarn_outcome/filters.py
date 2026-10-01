"""
Filters for the YarnOutcome module.
"""

import django_filters
from factory.yarn.yarn_intake.models import YarnOutcome


class YarnOutcomeFilter(django_filters.FilterSet):
    yarn_intake = django_filters.NumberFilter(field_name="yarn_intake__id")
    outcome_type = django_filters.ChoiceFilter(choices=YarnOutcome.OutcomeTypeChoices.choices)
    yarn_buyer = django_filters.NumberFilter(field_name="yarn_buyer__id")
    outcome_date_after = django_filters.DateFilter(field_name="outcome_date", lookup_expr="gte")
    outcome_date_before = django_filters.DateFilter(field_name="outcome_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = YarnOutcome
        fields = ["yarn_intake", "outcome_type", "yarn_buyer"]
