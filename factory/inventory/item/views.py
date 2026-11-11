"""
Views for the InventoryItem submodule.
"""

from decimal import Decimal

from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import InventoryItem
from .serializers import InventoryItemListSerializer, InventoryItemDetailSerializer
from .filters import InventoryItemFilter
from factory.inventory.ledger.serializers import InventoryLedgerSerializer


class InventoryItemViewSet(ModelViewSet):
    """
    CRUD for InventoryItem.

    Extra actions:
        GET /inventory/items/stats/       – aggregate stats
        GET /inventory/items/{id}/ledger/ – ledger entries for an item
    """

    queryset = (
        InventoryItem.objects
        .select_related("category", "unit", "preferred_supplier", "created_by", "updated_by")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InventoryItemFilter
    search_fields = ["item_name", "item_code", "description", "storage_location"]
    ordering_fields = ["item_name", "item_code", "current_stock", "created_at"]
    ordering = ["item_name"]

    permission_map = {
        "GET": ["inv.view", "inventory.view"],
        "POST": ["inv.add", "inventory.add"],
        "PUT": ["inv.edit", "inventory.change"],
        "PATCH": ["inv.edit", "inventory.change"],
        "DELETE": ["inv.delete", "inventory.delete"],
    }

    def get_serializer_class(self):
        if self.action == "list":
            return InventoryItemListSerializer
        return InventoryItemDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        log_activity(
            request=request,
            action="Create Inventory Item",
            description=f"Created inventory item '{instance.item_name}' ({instance.item_code}).",
            module="Inventory – Items",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Item created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            request=request,
            action="Update Inventory Item",
            description=f"Updated inventory item '{instance.item_name}' ({instance.item_code}).",
            module="Inventory – Items",
            status="Success",
        )
        return Response({"success": True, "message": "Item updated successfully.", "data": serializer.data})

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.item_name
        code = instance.item_code
        instance.delete()
        log_activity(
            request=request,
            action="Delete Inventory Item",
            description=f"Deleted inventory item '{name}' ({code}).",
            module="Inventory – Items",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Item deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Aggregate stats for all items."""
        qs = self.filter_queryset(self.get_queryset())
        total_items = qs.count()
        active_items = qs.filter(status=InventoryItem.StatusChoices.ACTIVE).count()
        low_stock_count = qs.filter(
            current_stock__gt=0,
            current_stock__lte=F("minimum_stock_level"),
        ).count()
        out_of_stock_count = qs.filter(current_stock__lte=0).count()
        total_value = qs.aggregate(
            val=Sum(
                ExpressionWrapper(
                    F("current_stock") * F("purchase_price"),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            )
        )["val"] or Decimal("0")

        return Response({
            "success": True,
            "data": {
                "totalItems": total_items,
                "activeItems": active_items,
                "lowStockCount": low_stock_count,
                "outOfStockCount": out_of_stock_count,
                "totalInventoryValue": str(total_value),
            },
        })

    @action(detail=True, methods=["get"], url_path="ledger")
    def ledger(self, request, pk=None):
        """Return all ledger entries for a specific item."""
        item = self.get_object()
        from factory.inventory.ledger.models import InventoryLedger

        entries = (
            InventoryLedger.objects
            .filter(inventory_item=item)
            .select_related("supplier", "created_by")
            .order_by("transaction_date", "id")
        )
        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = InventoryLedgerSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = InventoryLedgerSerializer(entries, many=True)
        return Response({"success": True, "data": serializer.data})
