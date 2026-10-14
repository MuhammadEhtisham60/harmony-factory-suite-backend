"""
Sizing Ledger API (read-only).

Endpoints (mounted under /api/v1/):
    GET /sizing-ledger/          -> paginated ledger rows with per-sizing running balances
    GET /sizing-ledger/summary/  -> totals + per-sizing closing balances for the same filters
    GET /sizing-ledger/export/   -> CSV of the filtered ledger (full-precision values)

Query params (all optional):
    sizing        sizing party id
    date_from     YYYY-MM-DD (inclusive)
    date_to       YYYY-MM-DD (inclusive)
    entry_type    income | outcome
    set_no        substring match on set number
    search        substring match on sizing / reference / set no / set bill / remarks
    ordering      date (default, oldest first) | -date (newest first)
    page, page_size   (list only; standard pagination)
"""

import csv

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission

from .ledger import (
    CSV_COLUMNS,
    ENTRY_TYPES,
    build_sizing_ledger,
    csv_value,
    summarize_ledger,
)
from .ledger_serializers import (
    BalanceSerializer,
    SizingLedgerPartySummarySerializer,
    SizingLedgerRowSerializer,
    SizingLedgerTotalsSerializer,
)


class SizingLedgerViewSet(ViewSet):
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    permission_map = {"GET": "sizing.view"}

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

        sizing_id = params.get("sizing")
        if sizing_id not in (None, ""):
            try:
                sizing_id = int(sizing_id)
            except (TypeError, ValueError):
                errors["sizing"] = "Sizing id must be an integer."
        else:
            sizing_id = None

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
            "sizing_id": sizing_id,
            "date_from": date_from,
            "date_to": date_to,
            "entry_type": entry_type,
            "set_no": params.get("set_no") or None,
            "search": params.get("search") or None,
            "descending": ordering == "-date",
        }

    # ── endpoints ──────────────────────────────────────────────────────────

    def list(self, request):
        rows, opening_balance = build_sizing_ledger(**self._parse_filters(request))

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        data = SizingLedgerRowSerializer(page, many=True).data
        response = paginator.get_paginated_response(data)
        response.data["openingBalance"] = (
            BalanceSerializer(opening_balance).data if opening_balance is not None else None
        )
        return response

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        rows, opening_balance = build_sizing_ledger(**self._parse_filters(request))
        summary = summarize_ledger(rows)
        return Response(
            {
                "success": True,
                "data": {
                    "totals": SizingLedgerTotalsSerializer(summary["totals"]).data,
                    "parties": SizingLedgerPartySummarySerializer(summary["parties"], many=True).data,
                    "openingBalance": (
                        BalanceSerializer(opening_balance).data if opening_balance is not None else None
                    ),
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        rows, _ = build_sizing_ledger(**self._parse_filters(request))

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="sizing-ledger.csv"'
        writer = csv.writer(response)
        writer.writerow([header for header, _key in CSV_COLUMNS])
        for row in rows:
            writer.writerow([csv_value(row.get(key)) for _header, key in CSV_COLUMNS])
        return response
