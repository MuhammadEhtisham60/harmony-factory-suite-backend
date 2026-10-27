"""
Warping Ledger API (read-only).

Endpoints (mounted under /api/v1/):
    GET /warping-ledger/          -> Main Warping Ledger (all warping records with per-warping counters & aggregate totals)
    GET /warping-ledger/{id}/     -> Individual Warping Ledger (warping details, transactions, per-warping counters & pagination)
    GET /warping-ledger/transactions/ -> Transaction-level ledger rows with running balances
    GET /warping-ledger/summary/  -> Totals + per-warping closing balances
    GET /warping-ledger/export/   -> CSV export (supports both main warping records and transactions)
"""

import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission

from .models import Warping
from .ledger import (
    CSV_COLUMNS,
    MAIN_CSV_COLUMNS,
    ENTRY_TYPES,
    ZERO,
    build_warping_ledger,
    csv_value,
    exact_str,
    get_main_warping_ledger,
    get_individual_warping_ledger_summary,
    summarize_ledger,
)
from .ledger_serializers import (
    BalanceSerializer,
    IndividualWarpingSummarySerializer,
    MainWarpingLedgerItemSerializer,
    MainWarpingLedgerSummarySerializer,
    WarpingDetailSummarySerializer,
    WarpingLedgerPartySummarySerializer,
    WarpingLedgerRowSerializer,
    WarpingLedgerTotalsSerializer,
)


class WarpingLedgerViewSet(ViewSet):
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    permission_map = {"GET": "warping.view"}

    # ── helpers ────────────────────────────────────────────────────────────

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

        warping_id = params.get("warping")
        if warping_id not in (None, ""):
            try:
                warping_id = int(warping_id)
            except (TypeError, ValueError):
                errors["warping"] = "Warping id must be an integer."
        else:
            warping_id = None

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
            "warping_id": warping_id,
            "date_from": date_from,
            "date_to": date_to,
            "entry_type": entry_type,
            "set_no": params.get("set_no") or None,
            "search": params.get("search") or None,
            "descending": ordering == "-date",
        }

    # ── Main Warping Ledger / Router List ───────────────────────────────────

    def list(self, request):
        """
        Main Warping Ledger API:
        Returns:
          - Paginated warping records
          - Total payables across all warping records matching current filters
          - Total boxes sent
          - Total boxes received
          - Total boxes in balance
          - Per-warping summary values for every row
        """
        params = request.query_params
        view_mode = params.get("view")
        warping_param = params.get("warping")

        # Validate entry_type if passed
        entry_type = params.get("entry_type") or None
        if entry_type is not None and entry_type not in ENTRY_TYPES:
            raise ValidationError({"entry_type": f"Must be one of: {', '.join(ENTRY_TYPES)}."})

        # If explicit transactions view requested, delegate to transactions action
        if view_mode == "transactions" or params.get("transactions") == "true":
            return self.transactions(request)

        # If warping parameter provided and view is not explicitly 'main', delegate to retrieve
        if warping_param not in (None, "") and view_mode != "main":
            try:
                w_id = int(warping_param)
            except (TypeError, ValueError):
                raise ValidationError({"warping": "Warping id must be an integer."})
            if not Warping.objects.filter(id=w_id).exists():
                return Response({
                    "success": True,
                    "count": 0,
                    "totalPages": 1,
                    "currentPage": 1,
                    "pageSize": 10,
                    "results": [],
                    "transactions": [],
                    "openingBalance": None,
                    "totalPayables": "0",
                    "totalBoxesSent": "0",
                    "totalBoxesReceived": "0",
                    "totalBoxesBalance": "0",
                })
            return self.retrieve(request, pk=warping_param)

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

        ordering_param = params.get("ordering") or "warping_name"
        valid_orderings = {
            "warping_name", "-warping_name", "status", "-status", "created_at", "-created_at",
            "total_boxes_sent", "-total_boxes_sent", "total_boxes_received", "-total_boxes_received",
            "total_boxes_balance", "-total_boxes_balance", "total_payables", "-total_payables",
            "total_charges", "-total_charges", "total_paid", "-total_paid",
            "transactions_count", "-transactions_count", "date", "-date",
        }
        if ordering_param not in valid_orderings:
            errors["ordering"] = f"Must be one of: {', '.join(sorted(valid_orderings))}."

        if errors:
            raise ValidationError(errors)

        status_filter = params.get("status") or None
        search_filter = params.get("search") or None

        warping_items, aggregate_totals = get_main_warping_ledger(
            search=search_filter,
            status=status_filter,
            date_from=date_from,
            date_to=date_to,
            ordering=ordering_param,
        )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(warping_items, request, view=self)
        results = MainWarpingLedgerItemSerializer(page, many=True).data

        response = paginator.get_paginated_response(results)
        response.data["openingBalance"] = None
        response.data["summary"] = MainWarpingLedgerSummarySerializer(aggregate_totals).data
        response.data["totalPayables"] = exact_str(aggregate_totals["total_payables"])
        response.data["totalCharges"] = exact_str(aggregate_totals.get("total_charges", ZERO))
        response.data["totalPaid"] = exact_str(aggregate_totals.get("total_paid", ZERO))
        response.data["totalBoxesSent"] = exact_str(aggregate_totals["total_boxes_sent"])
        response.data["totalBoxesReceived"] = exact_str(aggregate_totals["total_boxes_received"])
        response.data["totalBoxesBalance"] = exact_str(aggregate_totals["total_boxes_balance"])
        return response

    # ── Individual Warping Ledger ───────────────────────────────────────────

    def retrieve(self, request, pk=None):
        """
        Individual Warping Detail Ledger API:
        Returns:
          - Warping details
          - Transactions belonging only to this warping with running balances
          - Total payables for this warping
          - Total boxes sent
          - Total boxes received
          - Boxes in balance
          - Transaction pagination and supported filters
        """
        try:
            warping_id = int(pk)
        except (TypeError, ValueError):
            raise ValidationError({"detail": "Invalid warping ID. Must be an integer."})

        warping = get_object_or_404(Warping, pk=warping_id)

        filters = self._parse_filters(request)
        filters["warping_id"] = warping.id

        rows, opening_balance = build_warping_ledger(**filters)
        summary_totals = get_individual_warping_ledger_summary(
            warping_id=warping.id,
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
        )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        page_data = WarpingLedgerRowSerializer(page, many=True).data

        total_pages = paginator.page.paginator.num_pages if paginator.page else 1
        current_page = paginator.page.number if paginator.page else 1
        page_size = paginator.get_page_size(request) or paginator.page_size
        count = paginator.page.paginator.count if paginator.page else len(page_data)

        return Response({
            "success": True,
            "warping": WarpingDetailSummarySerializer(warping).data,
            "summary": IndividualWarpingSummarySerializer(summary_totals).data,
            "totalPayables": exact_str(summary_totals["total_payables"]),
            "totalCharges": exact_str(summary_totals.get("total_charges", ZERO)),
            "totalPaid": exact_str(summary_totals.get("total_paid", ZERO)),
            "totalBoxesSent": exact_str(summary_totals["total_boxes_sent"]),
            "totalBoxesReceived": exact_str(summary_totals["total_boxes_received"]),
            "totalBoxesBalance": exact_str(summary_totals["total_boxes_balance"]),
            "openingBalance": (
                BalanceSerializer(opening_balance).data if opening_balance is not None else None
            ),
            "count": count,
            "totalPages": total_pages,
            "currentPage": current_page,
            "pageSize": page_size,
            "results": page_data,
            "transactions": page_data,
        })

    # ── Transactions Stream ────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="transactions")
    def transactions(self, request):
        """Paginated chronological transactions stream with running balances."""
        filters = self._parse_filters(request)
        rows, opening_balance = build_warping_ledger(**filters)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        data = WarpingLedgerRowSerializer(page, many=True).data
        response = paginator.get_paginated_response(data)
        response.data["openingBalance"] = (
            BalanceSerializer(opening_balance).data if opening_balance is not None else None
        )
        return response

    # ── Summary ────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Aggregate totals and per-party summary."""
        filters = self._parse_filters(request)
        rows, opening_balance = build_warping_ledger(**filters)
        summary = summarize_ledger(rows)
        return Response(
            {
                "success": True,
                "data": {
                    "totals": WarpingLedgerTotalsSerializer(summary["totals"]).data,
                    "parties": WarpingLedgerPartySummarySerializer(summary["parties"], many=True).data,
                    "openingBalance": (
                        BalanceSerializer(opening_balance).data if opening_balance is not None else None
                    ),
                },
            }
        )

    # ── Export CSV ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """Export ledger data as CSV."""
        params = request.query_params
        export_mode = params.get("mode") or ("transactions" if params.get("warping") else "main")

        response = HttpResponse(content_type="text/csv")

        if export_mode == "transactions":
            filters = self._parse_filters(request)
            rows, _ = build_warping_ledger(**filters)
            response["Content-Disposition"] = 'attachment; filename="warping-ledger-transactions.csv"'
            writer = csv.writer(response)
            writer.writerow([header for header, _key in CSV_COLUMNS])
            for row in rows:
                writer.writerow([csv_value(row.get(key)) for _header, key in CSV_COLUMNS])
            return response

        # Default export: Main Warping Ledger CSV
        status_filter = params.get("status") or None
        search_filter = params.get("search") or None
        ordering_filter = params.get("ordering") or "warping_name"
        date_from = self._parse_date(params, "date_from") if params.get("date_from") else None
        date_to = self._parse_date(params, "date_to") if params.get("date_to") else None

        warping_items, _ = get_main_warping_ledger(
            search=search_filter,
            status=status_filter,
            date_from=date_from,
            date_to=date_to,
            ordering=ordering_filter,
        )
        response["Content-Disposition"] = 'attachment; filename="warping-ledger-summary.csv"'
        writer = csv.writer(response)
        writer.writerow([header for header, _key in MAIN_CSV_COLUMNS])
        for item in warping_items:
            writer.writerow([csv_value(item.get(key)) for _header, key in MAIN_CSV_COLUMNS])
        return response
