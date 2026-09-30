"""
FilterSet for the Supplier module.
"""

import django_filters
from .models import Supplier


class SupplierFilter(django_filters.FilterSet):
    """
    Filters for SupplierViewSet.

    Supported query params:
        - status          : exact match  (Active / Inactive / Blocked)
        - supplier_type   : exact match  (Yarn / Spare Parts / ...)
        - search          : icontains on supplier_name, company_name, supplier_code, phone, contact_person
        - created_after   : DateFilter – suppliers created on or after this date  (YYYY-MM-DD)
        - created_before  : DateFilter – suppliers created on or before this date (YYYY-MM-DD)
    """

    status = django_filters.ChoiceFilter(choices=Supplier.StatusChoices.choices)

    supplier_type = django_filters.ChoiceFilter(choices=Supplier.SupplierType.choices)

    # Free-text search across multiple fields
    search = django_filters.CharFilter(method="filter_search", label="Search")

    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Supplier
        fields = ["status", "supplier_type"]

    def filter_search(self, queryset, name, value):  # noqa: ARG002
        from django.db.models import Q

        return queryset.filter(
            Q(supplier_name__icontains=value)
            | Q(company_name__icontains=value)
            | Q(supplier_code__icontains=value)
            | Q(phone__icontains=value)
            | Q(contact_person__icontains=value)
            | Q(email__icontains=value)
        )
