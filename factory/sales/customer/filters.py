"""
FilterSet for the Customer module.
"""

import django_filters
from django.db.models import Q
from .models import Customer


class CustomerFilter(django_filters.FilterSet):
    """
    Supported query params:
        status          – exact  (Active / Inactive / Blocked)
        customer_type   – exact  (Wholesaler / Retailer / ...)
        search          – icontains on name, code, company, phone, email, contact_person
        created_after   – YYYY-MM-DD, customers created on or after
        created_before  – YYYY-MM-DD, customers created on or before
    """

    status = django_filters.ChoiceFilter(
        choices=Customer.StatusChoices.choices
    )

    customer_type = django_filters.ChoiceFilter(
        choices=Customer.CustomerType.choices
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

    class Meta:
        model = Customer
        fields = ["status", "customer_type"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(customer_name__icontains=value)
            | Q(customer_code__icontains=value)
            | Q(company_name__icontains=value)
            | Q(phone__icontains=value)
            | Q(email__icontains=value)
            | Q(contact_person__icontains=value)
        )
