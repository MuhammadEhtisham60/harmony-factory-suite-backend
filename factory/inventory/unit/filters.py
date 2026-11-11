"""
Filters for the InventoryUnit submodule.
"""

import django_filters
from .models import InventoryUnit


class InventoryUnitFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = InventoryUnit
        fields = ["is_active", "name"]
