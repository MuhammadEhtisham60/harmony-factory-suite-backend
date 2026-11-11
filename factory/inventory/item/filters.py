"""
Filters for the InventoryItem submodule.
"""

import django_filters
from .models import InventoryItem


class InventoryItemFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=InventoryItem.StatusChoices.choices)
    category = django_filters.NumberFilter(field_name="category_id")
    unit = django_filters.NumberFilter(field_name="unit_id")
    item_name = django_filters.CharFilter(field_name="item_name", lookup_expr="icontains")
    item_code = django_filters.CharFilter(field_name="item_code", lookup_expr="icontains")

    class Meta:
        model = InventoryItem
        fields = ["status", "category", "unit"]
