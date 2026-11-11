"""
Views for the InventoryLedger submodule – list and payment actions.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import InventoryLedger
from .serializers import InventoryLedgerSerializer, InventoryPaymentSerializer
from .filters import InventoryLedgerFilter
from factory.inventory.services import record_ledger_payment


class InventoryLedgerListView(ListAPIView):
    """
    List of all ledger entries with stock and payment summaries.

    Filters: item, category, supplier, transaction_type, payment_status, date_from, date_to
    """

    queryset = (
        InventoryLedger.objects
        .select_related(
            "inventory_item",
            "inventory_item__category",
            "inventory_item__unit",
            "inventory_item__preferred_supplier",
            "supplier",
            "created_by",
        )
        .prefetch_related(
            "payments__bank_account",
            "payments__supplier",
            "payments__created_by",
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
        "supplier__supplier_name",
        "notes",
    ]
    ordering_fields = ["transaction_date", "created_at", "total_amount", "amount_due"]
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
            total_amount=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            total_due=Sum("amount_due"),
            paid_count=Count("id", filter=Q(payment_status="Paid")),
            partially_paid_count=Count("id", filter=Q(payment_status="Partially Paid")),
            pending_count=Count("id", filter=Q(payment_status="Pending")),
        )
        total_in = totals["total_in"] or Decimal("0")
        total_out = totals["total_out"] or Decimal("0")
        total_amount = totals["total_amount"] or Decimal("0.00")
        total_paid = totals["total_paid"] or Decimal("0.00")
        total_due = totals["total_due"] or Decimal("0.00")

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
            "totalAmount": str(total_amount),
            "totalPaid": str(total_paid),
            "totalDue": str(total_due),
            "paidCount": totals["paid_count"] or 0,
            "partiallyPaidCount": totals["partially_paid_count"] or 0,
            "pendingCount": totals["pending_count"] or 0,
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


class InventoryLedgerPaymentView(APIView):
    """
    POST /api/v1/inventory/ledger/<int:pk>/pay/
    POST /api/v1/inventory/ledger/pay/
    Record a payment and/or update payment status ('Pending', 'Partially Paid', 'Paid')
    for an InventoryLedger entry.
    """

    permission_classes = [IsAuthenticated, HasERPModulePermission]
    permission_map = {
        "POST": ["inv.add", "inv.edit", "inventory.add", "inventory.change", "po.add", "po.edit"],
    }

    def post(self, request, pk=None):
        entry_id = pk or request.data.get("ledgerEntryId") or request.data.get("id")
        if not entry_id:
            return Response(
                {"success": False, "message": "Ledger entry ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ledger_entry = get_object_or_404(
            InventoryLedger.objects.select_related(
                "inventory_item", "supplier", "inventory_item__preferred_supplier"
            ),
            pk=entry_id,
        )

        try:
            updated_entry, payment_obj = record_ledger_payment(
                ledger_entry=ledger_entry,
                data=request.data,
                user=request.user,
            )
        except Exception as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            request=request,
            action="Record Inventory Ledger Payment",
            description=(
                f"Updated payment for '{updated_entry.transaction_number}' "
                f"(Status: {updated_entry.payment_status}, Paid: Rs. {updated_entry.amount_paid})."
            ),
            module="Inventory – Ledger",
            status="Success",
        )

        serializer = InventoryLedgerSerializer(updated_entry)
        return Response(
            {
                "success": True,
                "message": "Payment and status updated successfully.",
                "data": serializer.data,
                "payment": InventoryPaymentSerializer(payment_obj).data if payment_obj else None,
            },
            status=status.HTTP_200_OK,
        )


