"""
Filters for the InventoryPurchase submodule.
"""

import django_filters
from .models import InventoryPurchase


class InventoryPurchaseFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=InventoryPurchase.StatusChoices.choices)
    payment_status = django_filters.ChoiceFilter(
        choices=InventoryPurchase.PaymentStatusChoices.choices
    )
    supplier = django_filters.NumberFilter(field_name="supplier_id")
    date_from = django_filters.DateFilter(field_name="purchase_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="purchase_date", lookup_expr="lte")
    purchase_number = django_filters.CharFilter(
        field_name="purchase_number", lookup_expr="icontains"
    )

    class Meta:
        model = InventoryPurchase
        fields = ["status", "payment_status", "supplier"]
