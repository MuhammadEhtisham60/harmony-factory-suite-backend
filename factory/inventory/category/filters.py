"""
Filters for the InventoryCategory submodule.
"""

import django_filters
from .models import InventoryCategory


class InventoryCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = InventoryCategory
        fields = ["is_active", "name"]
