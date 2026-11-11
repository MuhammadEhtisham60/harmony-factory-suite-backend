"""
Filters for the InventoryLedger submodule.
"""

import django_filters
from .models import InventoryLedger


class InventoryLedgerFilter(django_filters.FilterSet):
    item = django_filters.NumberFilter(field_name="inventory_item_id")
    category = django_filters.NumberFilter(field_name="inventory_item__category_id")
    supplier = django_filters.NumberFilter(field_name="supplier_id")
    transaction_type = django_filters.ChoiceFilter(
        field_name="transaction_type",
        choices=InventoryLedger.TransactionTypeChoices.choices,
    )
    payment_status = django_filters.ChoiceFilter(
        field_name="payment_status",
        choices=InventoryLedger.PaymentStatusChoices.choices,
    )
    date_from = django_filters.DateFilter(field_name="transaction_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="transaction_date", lookup_expr="lte")

    class Meta:
        model = InventoryLedger
        fields = ["item", "category", "supplier", "transaction_type", "payment_status"]
