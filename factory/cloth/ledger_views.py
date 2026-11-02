"""
Inventory Ledger API Views.

Endpoints:
    GET  /api/v1/inventory-ledger/                  -> Main Stock Ledger (quality summary & totals)
    GET  /api/v1/inventory-ledger/{id}/             -> Individual Quality Ledger (running balances & transactions)
    GET  /api/v1/inventory-ledger/summary/          -> Global summary KPI statistics
    GET  /api/v1/inventory-ledger/movements/        -> Flat chronological movements stream with pagination
    POST /api/v1/inventory-ledger/movements/        -> Record incoming/outgoing stock movement
    DELETE /api/v1/inventory-ledger/movements/{id}/ -> Delete a manual stock movement
    GET  /api/v1/inventory-ledger/export/           -> Export CSV (main summary or individual ledger)
"""

from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from .models import ClothStock, ClothStockMovement
from .serializers import ClothStockMovementSerializer
from .services import delete_cloth_stock_movement
from .ledger import (
    get_main_inventory_ledger,
    build_individual_inventory_ledger,
    export_inventory_ledger_csv,
    ENTRY_TYPES,
)


class InventoryLedgerViewSet(ViewSet):
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    required_permission = "inv.view"

    permission_map = {
        "GET": "inv.view",
        "POST": "inv.view",
        "DELETE": "inv.view",
    }

    @staticmethod
    def _parse_date(params, key):
        raw = params.get(key)
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            raise ValidationError({key: "Enter a valid date in YYYY-MM-DD format."})
        return parsed

    def list(self, request):
        """
        GET /api/v1/inventory-ledger/
        Main Inventory Stock Ledger: lists all cloth qualities with current stock,
        incoming, outgoing, bundle counts, and aggregated KPIs.
        """
        params = request.query_params
        date_from = self._parse_date(params, "date_from")
        date_to = self._parse_date(params, "date_to")
        search = params.get("search", "").strip()
        ordering = params.get("ordering", "cloth_name")

        res = get_main_inventory_ledger(
            date_from=date_from,
            date_to=date_to,
            search=search,
            ordering=ordering
        )

        rows = res["rows"]
        summary = res["summary"]

        # Pagination
        try:
            page = max(1, int(params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = max(1, min(200, int(params.get("page_size", 10))))
        except (ValueError, TypeError):
            page_size = 10

        total_count = len(rows)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_rows = rows[start_idx:end_idx]
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        return Response({
            "success": True,
            "count": total_count,
            "totalPages": total_pages,
            "currentPage": page,
            "pageSize": page_size,
            "summary": summary,
            "results": paginated_rows,
            "data": paginated_rows,
        })

    def retrieve(self, request, pk=None):
        """
        GET /api/v1/inventory-ledger/{id}/
        Individual Cloth Quality Ledger: provides chronological incoming/outgoing
        movements and exact running stock balances.
        """
        params = request.query_params
        date_from = self._parse_date(params, "date_from")
        date_to = self._parse_date(params, "date_to")
        movement_type = params.get("movement_type") or params.get("movementType")
        if movement_type and movement_type not in ENTRY_TYPES:
            raise ValidationError({"movement_type": f"Must be one of: {', '.join(ENTRY_TYPES)}."})

        search = params.get("search", "").strip()
        ordering = params.get("ordering", "-date")

        try:
            stock = ClothStock.objects.get(id=pk)
        except (ClothStock.DoesNotExist, ValueError):
            return Response(
                {"success": False, "message": f"ClothStock #{pk} does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        res = build_individual_inventory_ledger(
            cloth_stock_id=stock.id,
            date_from=date_from,
            date_to=date_to,
            movement_type=movement_type,
            search=search,
            ordering=ordering,
        )

        return Response({
            "success": True,
            "data": res,
            "cloth": res["cloth"],
            "summary": res["summary"],
            "results": res["rows"],
        })

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        GET /api/v1/inventory-ledger/summary/
        Returns aggregated high-level KPIs across all cloth inventory.
        """
        params = request.query_params
        date_from = self._parse_date(params, "date_from")
        date_to = self._parse_date(params, "date_to")
        res = get_main_inventory_ledger(date_from=date_from, date_to=date_to)
        return Response({
            "success": True,
            "data": res["summary"],
            "summary": res["summary"],
        })

    @action(detail=False, methods=["get", "post"], url_path="movements")
    def movements(self, request):
        """
        GET /api/v1/inventory-ledger/movements/ -> List all stock movements
        POST /api/v1/inventory-ledger/movements/ -> Record new stock movement (incoming or outgoing)
        """
        if request.method == "POST":
            serializer = ClothStockMovementSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            out = ClothStockMovementSerializer(instance, context={"request": request})
            m_type = instance.movement_type
            action_desc = "dispatched" if m_type == ClothStockMovement.MovementType.OUTGOING else "received"
            return Response({
                "success": True,
                "message": f"Stock movement of {instance.quantity}m {action_desc} successfully.",
                "data": out.data,
            }, status=status.HTTP_201_CREATED)

        # GET: List movements with pagination & filters
        params = request.query_params
        qs = ClothStockMovement.objects.select_related("cloth_stock__cloth_name", "created_by").all()

        stock_id = params.get("cloth_stock") or params.get("clothStockId") or params.get("cloth_stock_id")
        if stock_id:
            qs = qs.filter(cloth_stock_id=stock_id)

        m_type = params.get("movement_type") or params.get("movementType")
        if m_type:
            qs = qs.filter(movement_type=m_type)

        sub_type = params.get("sub_type") or params.get("subType")
        if sub_type:
            qs = qs.filter(sub_type=sub_type)

        date_from = self._parse_date(params, "date_from")
        if date_from:
            qs = qs.filter(transaction_date__gte=date_from)

        date_to = self._parse_date(params, "date_to")
        if date_to:
            qs = qs.filter(transaction_date__lte=date_to)

        search = params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(reference_number__icontains=search) |
                Q(party_name__icontains=search) |
                Q(cloth_stock__cloth_name__name__icontains=search) |
                Q(sub_type__icontains=search) |
                Q(remarks__icontains=search)
            )

        ordering = params.get("ordering", "-transaction_date")
        if ordering in ("date", "transaction_date"):
            qs = qs.order_by("transaction_date", "id")
        elif ordering in ("-date", "-transaction_date"):
            qs = qs.order_by("-transaction_date", "-id")
        elif ordering in ("quantity", "-quantity"):
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-transaction_date", "-id")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ClothStockMovementSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=["delete"], url_path=r"movements/(?P<movement_id>[^/.]+)")
    def delete_movement(self, request, movement_id=None):
        """
        DELETE /api/v1/inventory-ledger/movements/{id}/
        Deletes a manual stock movement and resynchronizes ClothStock.
        """
        delete_cloth_stock_movement(movement_or_id=movement_id, user=request.user, request=request)
        return Response({
            "success": True,
            "message": f"Stock movement #{movement_id} deleted successfully.",
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """
        GET /api/v1/inventory-ledger/export/
        Exports stock ledger summary or individual ledger as CSV.
        """
        params = request.query_params
        stock_id = params.get("cloth_stock") or params.get("clothStockId") or params.get("id")
        date_from = self._parse_date(params, "date_from")
        date_to = self._parse_date(params, "date_to")

        return export_inventory_ledger_csv(
            cloth_stock_id=stock_id,
            date_from=date_from,
            date_to=date_to,
        )

