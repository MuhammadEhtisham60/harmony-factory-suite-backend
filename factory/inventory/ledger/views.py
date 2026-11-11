"""
Views for the InventoryLedger submodule – read-only.
"""

from decimal import Decimal
from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission

from .models import InventoryLedger
from .serializers import InventoryLedgerSerializer
from .filters import InventoryLedgerFilter


class InventoryLedgerListView(ListAPIView):
    """
    Read-only list of all ledger entries.

    Filters: item, category, supplier, transaction_type, date_from, date_to
    """

    queryset = (
        InventoryLedger.objects
        .select_related(
            "inventory_item",
            "inventory_item__category",
            "inventory_item__unit",
            "supplier",
            "created_by",
        )
        .all()
    )
    serializer_class = InventoryLedgerSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InventoryLedgerFilter
    search_fields = [
        "transaction_number",
        "inventory_item__item_name",
        "inventory_item__item_code",
        "notes",
    ]
    ordering_fields = ["transaction_date", "created_at"]
    ordering = ["-transaction_date", "-id"]

    permission_map = {
        "GET": ["inv.view", "inventory.view"],
    }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Totals across filtered rows
        totals = queryset.aggregate(
            total_in=Sum("quantity_in"),
            total_out=Sum("quantity_out"),
        )
        total_in = totals["total_in"] or Decimal("0")
        total_out = totals["total_out"] or Decimal("0")

        item_id = request.query_params.get("item")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        opening_stock = Decimal("0")
        closing_stock = Decimal("0")

        if item_id:
            if date_from:
                prev_entry = (
                    InventoryLedger.objects
                    .filter(inventory_item_id=item_id, transaction_date__lt=date_from)
                    .order_by("-transaction_date", "-id")
                    .first()
                )
                opening_stock = prev_entry.running_balance if prev_entry else Decimal("0")
            else:
                first_entry = (
                    InventoryLedger.objects
                    .filter(inventory_item_id=item_id)
                    .order_by("transaction_date", "id")
                    .first()
                )
                opening_stock = (
                    first_entry.running_balance - first_entry.quantity_in + first_entry.quantity_out
                ) if first_entry else Decimal("0")

            last_entry_qs = InventoryLedger.objects.filter(inventory_item_id=item_id)
            if date_to:
                last_entry_qs = last_entry_qs.filter(transaction_date__lte=date_to)
            last_entry = last_entry_qs.order_by("-transaction_date", "-id").first()
            closing_stock = last_entry.running_balance if last_entry else Decimal("0")

        summary_data = {
            "totalIn": str(total_in),
            "totalOut": str(total_out),
            "netMovement": str(total_in - total_out),
            "openingStock": str(opening_stock),
            "closingStock": str(closing_stock),
        }

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            resp = self.get_paginated_response(serializer.data)
            resp.data["summary"] = summary_data
            return resp

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "results": serializer.data,
            "summary": summary_data,
        })

