"""
Views for the InventoryTransaction submodule.
"""

from rest_framework import status
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

from .models import InventoryTransaction
from .serializers import InventoryTransactionSerializer
from .filters import InventoryTransactionFilter
from factory.inventory.services import process_transaction


class InventoryTransactionViewSet(ModelViewSet):
    """
    CRUD for InventoryTransaction.

    On create, process_transaction service is called to update stock and
    create the ledger entry atomically.
    """

    queryset = (
        InventoryTransaction.objects
        .select_related("inventory_item", "created_by")
        .all()
    )
    serializer_class = InventoryTransactionSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InventoryTransactionFilter
    search_fields = ["transaction_number", "issued_to", "related_area", "notes"]
    ordering_fields = ["transaction_date", "created_at"]
    ordering = ["-transaction_date"]

    permission_map = {
        "GET": ["inv.view", "inventory.view"],
        "POST": ["inv.add", "inventory.add", "inv.adjust"],
        "PUT": ["inv.edit", "inventory.change", "inv.adjust"],
        "PATCH": ["inv.edit", "inventory.change", "inv.adjust"],
        "DELETE": ["inv.delete", "inventory.delete"],
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Save the transaction record first (assigns transaction_number)
        instance = serializer.save(
            created_by=request.user if request.user.is_authenticated else None
        )
        # Then process stock changes via the service
        try:
            process_transaction(instance, created_by=request.user)
        except DjangoValidationError as exc:
            # Roll back the transaction record if stock processing fails
            instance.delete()
            raise DRFValidationError({"detail": exc.message})

        log_activity(
            request=request,
            action="Create Inventory Transaction",
            description=(
                f"Transaction '{instance.transaction_number}' – "
                f"{instance.transaction_type} of {instance.quantity} "
                f"for {instance.inventory_item.item_name}."
            ),
            module="Inventory – Transactions",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Transaction recorded successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        return Response(
            {"success": False, "message": "Transactions cannot be edited."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"success": False, "message": "Transactions cannot be deleted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
