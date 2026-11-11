"""
Filters for the InventoryTransaction submodule.
"""

import django_filters
from .models import InventoryTransaction


class InventoryTransactionFilter(django_filters.FilterSet):
    transaction_type = django_filters.ChoiceFilter(
        field_name="transaction_type",
        choices=InventoryTransaction.TransactionTypeChoices.choices,
    )
    inventory_item = django_filters.NumberFilter(field_name="inventory_item_id")
    date_from = django_filters.DateFilter(field_name="transaction_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="transaction_date", lookup_expr="lte")

    class Meta:
        model = InventoryTransaction
        fields = ["transaction_type", "inventory_item"]
