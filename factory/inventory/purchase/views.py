"""
Views for the InventoryPurchase submodule.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import InventoryPurchase
from .serializers import InventoryPurchaseSerializer
from .filters import InventoryPurchaseFilter
from factory.inventory.services import confirm_purchase


class InventoryPurchaseViewSet(ModelViewSet):
    """
    CRUD for InventoryPurchase (with nested line items).

    Extra actions:
        POST /inventory/purchases/{id}/confirm/ – confirm purchase & update stock
    """

    queryset = (
        InventoryPurchase.objects
        .select_related("supplier", "created_by")
        .prefetch_related("items__inventory_item")
        .all()
    )
    serializer_class = InventoryPurchaseSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InventoryPurchaseFilter
    search_fields = ["purchase_number", "reference_number", "supplier__supplier_name"]
    ordering_fields = ["purchase_date", "created_at", "total_amount"]
    ordering = ["-purchase_date"]

    permission_map = {
        "GET": ["inv.view", "inventory.view", "po.view"],
        "POST": ["inv.add", "inventory.add", "po.add"],
        "PUT": ["inv.edit", "inventory.change", "po.edit"],
        "PATCH": ["inv.edit", "inventory.change", "po.edit"],
        "DELETE": ["inv.delete", "inventory.delete", "po.delete"],
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        log_activity(
            request=request,
            action="Create Inventory Purchase",
            description=f"Created purchase '{instance.purchase_number}'.",
            module="Inventory – Purchases",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Purchase created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if instance.status == "Confirmed":
            return Response(
                {"success": False, "message": "Cannot edit a confirmed purchase."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            request=request,
            action="Update Inventory Purchase",
            description=f"Updated purchase '{instance.purchase_number}'.",
            module="Inventory – Purchases",
            status="Success",
        )
        return Response({"success": True, "message": "Purchase updated successfully.", "data": serializer.data})

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == "Confirmed":
            return Response(
                {"success": False, "message": "Cannot delete a confirmed purchase."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        number = instance.purchase_number
        instance.delete()
        log_activity(
            request=request,
            action="Delete Inventory Purchase",
            description=f"Deleted purchase '{number}'.",
            module="Inventory – Purchases",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Purchase deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """
        Confirm a Draft purchase: creates ledger entries and updates current_stock
        for every line item.
        """
        purchase = self.get_object()
        try:
            confirm_purchase(purchase, confirmed_by=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.message})

        log_activity(
            request=request,
            action="Confirm Inventory Purchase",
            description=f"Confirmed purchase '{purchase.purchase_number}'.",
            module="Inventory – Purchases",
            status="Success",
        )
        serializer = self.get_serializer(purchase)
        return Response({
            "success": True,
            "message": "Purchase confirmed successfully.",
            "data": serializer.data,
        })
