"""
Yarn Supplier Ledger API Views.

Endpoints:
    GET  /api/v1/yarn-supplier-ledger/          -> Main Yarn Supplier Ledger (all suppliers with balances & aggregates)
    GET  /api/v1/yarn-supplier-ledger/{id}/     -> Individual Supplier Ledger (transactions, running balances, opening balance)
    GET  /api/v1/yarn-supplier-ledger/transactions/ -> Flat chronological transactions stream
    POST /api/v1/yarn-supplier-ledger/payments/ -> Record a payment to a yarn supplier
    GET  /api/v1/yarn-supplier-ledger/export/   -> CSV export (main summary or individual transactions)
"""

import csv
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from accounts.pagination import StandardResultsSetPagination
from factory.purchase.supplier.models import Supplier
from .models import YarnSupplierPayment
from .ledger import (
    CSV_COLUMNS,
    MAIN_CSV_COLUMNS,
    ENTRY_TYPES,
    ZERO,
    build_yarn_supplier_ledger,
    csv_value,
    exact_str,
    get_main_yarn_supplier_ledger,
)
from .serializers import (
    IndividualSupplierLedgerSummarySerializer,
    MainSupplierLedgerItemSerializer,
    MainSupplierLedgerSummarySerializer,
    SupplierLedgerBalanceSerializer,
    SupplierLedgerRowSerializer,
    YarnSupplierPaymentSerializer,
)


class YarnSupplierLedgerViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _parse_date(params, key):
        raw = params.get(key)
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            raise ValidationError({key: "Enter a valid date in YYYY-MM-DD format."})
        return parsed

    def _parse_filters(self, request):
        params = request.query_params
        errors = {}

        supplier_id = params.get("supplier") or params.get("supplier_id")
        if supplier_id not in (None, ""):
            try:
                supplier_id = int(supplier_id)
            except (TypeError, ValueError):
                errors["supplier"] = "Supplier id must be an integer."
        else:
            supplier_id = None

        entry_type = params.get("entry_type") or None
        if entry_type is not None and entry_type not in ENTRY_TYPES:
            errors["entry_type"] = f"Must be one of: {', '.join(ENTRY_TYPES)}."

        ordering = params.get("ordering") or "date"
        if ordering not in ("date", "-date"):
            errors["ordering"] = "Must be 'date' or '-date'."

        try:
            date_from = self._parse_date(params, "date_from")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_from = None
        try:
            date_to = self._parse_date(params, "date_to")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_to = None

        if not errors and date_from and date_to and date_from > date_to:
            errors["date_from"] = "date_from cannot be after date_to."

        if errors:
            raise ValidationError(errors)

        return {
            "supplier_id": supplier_id,
            "date_from": date_from,
            "date_to": date_to,
            "entry_type": entry_type,
            "search": params.get("search") or None,
            "descending": ordering == "-date",
        }

    # ── Main Yarn Supplier Ledger ─────────────────────────────────────────────

    def list(self, request):
        """
        Main Yarn Supplier Ledger:
        Lists all yarn suppliers with per-supplier counters and top-level summary totals.
        """
        params = request.query_params
        view_mode = params.get("view")
        supplier_param = params.get("supplier") or params.get("supplier_id")

        if view_mode == "transactions" or params.get("transactions") == "true":
            return self.transactions(request)

        if supplier_param not in (None, "") and view_mode != "main":
            try:
                s_id = int(supplier_param)
            except (TypeError, ValueError):
                raise ValidationError({"supplier": "Supplier id must be an integer."})
            if not Supplier.objects.filter(id=s_id).exists():
                return Response({
                    "success": True,
                    "count": 0,
                    "totalPages": 1,
                    "currentPage": 1,
                    "pageSize": 10,
                    "results": [],
                    "transactions": [],
                    "openingBalance": None,
                    "totalPurchases": "0",
                    "totalPaid": "0",
                    "totalPayables": "0",
                    "totalBagsReceived": "0",
                    "totalRemainingBags": "0",
                })
            return self.retrieve(request, pk=supplier_param)

        errors = {}
        try:
            date_from = self._parse_date(params, "date_from")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_from = None
        try:
            date_to = self._parse_date(params, "date_to")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_to = None

        if not errors and date_from and date_to and date_from > date_to:
            errors["date_from"] = "date_from cannot be after date_to."

        ordering = params.get("ordering") or "supplier_name"
        valid_orderings = {
            "supplier_name", "-supplier_name", "supplier_code", "-supplier_code",
            "status", "-status", "total_bags_received", "-total_bags_received",
            "total_remaining_bags", "-total_remaining_bags", "total_purchases", "-total_purchases",
            "total_paid", "-total_paid", "total_payables", "-total_payables",
            "transactions_count", "-transactions_count",
        }
        if ordering not in valid_orderings:
            ordering = "supplier_name"

        if errors:
            raise ValidationError(errors)

        search_filter = params.get("search") or None
        status_filter = params.get("status") or None

        supplier_items, aggregate_totals = get_main_yarn_supplier_ledger(
            search=search_filter,
            status=status_filter,
            date_from=date_from,
            date_to=date_to,
            ordering=ordering,
        )

        # Pagination
        paginator = StandardResultsSetPagination()
        paginated_items = paginator.paginate_queryset(supplier_items, request, view=self)

        serializer = MainSupplierLedgerItemSerializer(paginated_items, many=True)
        summary_ser = MainSupplierLedgerSummarySerializer(aggregate_totals).data

        page_obj = getattr(paginator, "page", None)
        total_pages = page_obj.paginator.num_pages if page_obj else 1
        current_page = page_obj.number if page_obj else 1

        return Response({
            "success": True,
            "count": len(supplier_items),
            "totalPages": total_pages,
            "currentPage": current_page,
            "pageSize": paginator.get_page_size(request),
            "results": serializer.data,
            "data": serializer.data,
            "summary": summary_ser,
            # Top-level direct counters for convenient UI binding
            "totalPurchases": summary_ser["totalPurchases"],
            "totalPaid": summary_ser["totalPaid"],
            "totalPayables": summary_ser["totalPayables"],
            "totalBagsReceived": summary_ser["totalBagsReceived"],
            "totalRemainingBags": summary_ser["totalRemainingBags"],
            "totalWeightKgReceived": summary_ser["totalWeightKgReceived"],
            "totalRemainingWeightKg": summary_ser["totalRemainingWeightKg"],
        })

    # ── Individual Yarn Supplier Detail Ledger ────────────────────────────────

    def retrieve(self, request, pk=None):
        """
        Individual Supplier Ledger:
        Returns supplier details, summary metrics, opening balance, and chronological transaction entries with running balances.
        """
        supplier = get_object_or_404(Supplier, pk=pk)
        filters = self._parse_filters(request)

        rows, opening_bal, closing_bal, summary = build_yarn_supplier_ledger(
            supplier_id=supplier.id,
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            entry_type=filters["entry_type"],
            search=filters["search"],
            descending=filters["descending"],
        )

        paginator = StandardResultsSetPagination()
        paginated_rows = paginator.paginate_queryset(rows, request, view=self)

        rows_ser = SupplierLedgerRowSerializer(paginated_rows, many=True).data
        opening_ser = SupplierLedgerBalanceSerializer(opening_bal).data
        closing_ser = SupplierLedgerBalanceSerializer(closing_bal).data
        summary_ser = IndividualSupplierLedgerSummarySerializer(summary).data

        page_obj = getattr(paginator, "page", None)
        total_pages = page_obj.paginator.num_pages if page_obj else 1
        current_page = page_obj.number if page_obj else 1

        bank_accounts = [
            {
                "id": b.id,
                "bankName": b.bank_name,
                "accountTitle": b.account_title,
                "accountNumber": b.account_number,
                "iban": b.iban,
                "isPrimary": b.is_primary,
            }
            for b in supplier.bank_accounts.all()
        ]

        supplier_detail = {
            "id": supplier.id,
            "supplierCode": supplier.supplier_code,
            "supplierName": supplier.supplier_name,
            "companyName": supplier.company_name or "",
            "contactPerson": supplier.contact_person or "",
            "phone": supplier.phone or "",
            "email": supplier.email or "",
            "address": supplier.address or "",
            "status": supplier.status,
            "supplierType": supplier.supplier_type,
            "registrationNumber": supplier.registration_number or "",
            "bankAccounts": bank_accounts,
        }

        return Response({
            "success": True,
            "supplier": supplier_detail,
            "count": len(rows),
            "totalPages": total_pages,
            "currentPage": current_page,
            "pageSize": paginator.get_page_size(request),
            "results": rows_ser,
            "data": rows_ser,
            "transactions": rows_ser,
            "openingBalance": opening_ser,
            "closingBalance": closing_ser,
            "summary": summary_ser,
            "totalPurchases": summary_ser["totalPurchases"],
            "totalPaid": summary_ser["totalPaid"],
            "totalPayables": summary_ser["totalPayables"],
            "totalBagsReceived": summary_ser["totalBagsReceived"],
            "totalRemainingBags": summary_ser["totalRemainingBags"],
        })

    # ── Flat Transactions Stream ──────────────────────────────────────────────

    @action(detail=False, methods=["GET"])
    def transactions(self, request):
        filters = self._parse_filters(request)
        if filters["supplier_id"]:
            return self.retrieve(request, pk=filters["supplier_id"])

        # Across all suppliers
        sup_ids = list(Supplier.objects.values_list("id", flat=True))
        all_rows = []
        for sid in sup_ids:
            rows, _, _, _ = build_yarn_supplier_ledger(
                supplier_id=sid,
                date_from=filters["date_from"],
                date_to=filters["date_to"],
                entry_type=filters["entry_type"],
                search=filters["search"],
                descending=False,
            )
            all_rows.extend(rows)

        all_rows.sort(
            key=lambda r: (r["date"], r["_rank"], r["_created_at"] or r["date"], r["_pk"]),
            reverse=filters["descending"],
        )

        paginator = StandardResultsSetPagination()
        paginated_rows = paginator.paginate_queryset(all_rows, request, view=self)
        rows_ser = SupplierLedgerRowSerializer(paginated_rows, many=True).data

        page_obj = getattr(paginator, "page", None)
        total_pages = page_obj.paginator.num_pages if page_obj else 1
        current_page = page_obj.number if page_obj else 1

        return Response({
            "success": True,
            "count": len(all_rows),
            "totalPages": total_pages,
            "currentPage": current_page,
            "pageSize": paginator.get_page_size(request),
            "results": rows_ser,
            "transactions": rows_ser,
        })

    # ── Record Payment Endpoint ───────────────────────────────────────────────

    @action(detail=False, methods=["GET", "POST"])
    def payments(self, request):
        if request.method == "POST":
            serializer = YarnSupplierPaymentSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            payment = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Payment recorded successfully",
                    "data": YarnSupplierPaymentSerializer(payment).data,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            supplier_id = request.query_params.get("supplier") or request.query_params.get("supplier_id")
            qs = YarnSupplierPayment.objects.all().select_related("supplier", "bank_account", "yarn_intake")
            if supplier_id:
                qs = qs.filter(supplier_id=supplier_id)
            paginator = StandardResultsSetPagination()
            page = paginator.paginate_queryset(qs, request, view=self)
            ser = YarnSupplierPaymentSerializer(page, many=True)
            return paginator.get_paginated_response(ser.data)

    # ── Export CSV ────────────────────────────────────────────────────────────

    @action(detail=False, methods=["GET"])
    def export(self, request):
        params = request.query_params
        supplier_param = params.get("supplier") or params.get("supplier_id")

        if supplier_param not in (None, ""):
            # Individual Supplier Statement CSV
            supplier = get_object_or_404(Supplier, pk=supplier_param)
            filters = self._parse_filters(request)
            rows, opening_bal, closing_bal, summary = build_yarn_supplier_ledger(
                supplier_id=supplier.id,
                date_from=filters["date_from"],
                date_to=filters["date_to"],
                entry_type=filters["entry_type"],
                search=filters["search"],
                descending=filters["descending"],
            )

            response = HttpResponse(content_type="text/csv")
            filename = f"supplier-ledger-{supplier.supplier_code}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow([f"YARN SUPPLIER LEDGER STATEMENT - {supplier.supplier_name} ({supplier.supplier_code})"])
            writer.writerow([f"Phone: {supplier.phone}", f"Email: {supplier.email}", f"Company: {supplier.company_name}"])
            writer.writerow([])
            writer.writerow([
                "Opening Payables", exact_str(opening_bal["balance_payables"]),
                "Opening Bags", exact_str(opening_bal["balance_bags"]),
                "Total Purchases", exact_str(summary["total_purchases"]),
                "Total Paid", exact_str(summary["total_paid"]),
                "Net Closing Payables", exact_str(closing_bal["balance_payables"]),
            ])
            writer.writerow([])

            headers = [h for h, _ in CSV_COLUMNS]
            writer.writerow(headers)
            for r in rows:
                writer.writerow([csv_value(r.get(k)) for _, k in CSV_COLUMNS])

            return response
        else:
            # Main Supplier Summary CSV
            filters = self._parse_filters(request)
            supplier_items, agg = get_main_yarn_supplier_ledger(
                search=filters.get("search"),
                status=params.get("status"),
                date_from=filters["date_from"],
                date_to=filters["date_to"],
                ordering=params.get("ordering") or "supplier_name",
            )

            response = HttpResponse(content_type="text/csv")
            filename = "yarn-supplier-ledger-summary.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow(["YARN SUPPLIERS LEDGER SUMMARY"])
            writer.writerow([
                "Total Suppliers", str(agg["suppliers_count"]),
                "Total Bags Received", exact_str(agg["total_bags_received"]),
                "Total Remaining Bags", exact_str(agg["total_remaining_bags"]),
                "Total Purchases", exact_str(agg["total_purchases"]),
                "Total Paid", exact_str(agg["total_paid"]),
                "Total Outstanding Payables", exact_str(agg["total_payables"]),
            ])
            writer.writerow([])

            headers = [h for h, _ in MAIN_CSV_COLUMNS]
            writer.writerow(headers)
            for r in supplier_items:
                writer.writerow([csv_value(r.get(k)) for _, k in MAIN_CSV_COLUMNS])

            return response
