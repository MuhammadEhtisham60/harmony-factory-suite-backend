"""
Views for the InventoryCategory submodule.
"""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import InventoryCategory
from .serializers import InventoryCategorySerializer
from .filters import InventoryCategoryFilter


class InventoryCategoryViewSet(ModelViewSet):
    """
    CRUD for InventoryCategory.

    Endpoints (router-generated):
        GET    /inventory/categories/        – list
        POST   /inventory/categories/        – create
        GET    /inventory/categories/{id}/   – retrieve
        PUT    /inventory/categories/{id}/   – update
        PATCH  /inventory/categories/{id}/   – partial update
        DELETE /inventory/categories/{id}/   – destroy
    """

    queryset = InventoryCategory.objects.select_related("created_by").all()
    serializer_class = InventoryCategorySerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InventoryCategoryFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    permission_map = {
        "GET": ["inv.view", "inventory.view"],
        "POST": ["inv.add", "inventory.add"],
        "PUT": ["inv.edit", "inventory.change"],
        "PATCH": ["inv.edit", "inventory.change"],
        "DELETE": ["inv.delete", "inventory.delete"],
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        log_activity(
            request=request,
            action="Create Inventory Category",
            description=f"Created inventory category '{instance.name}'.",
            module="Inventory – Categories",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Category created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            request=request,
            action="Update Inventory Category",
            description=f"Updated inventory category '{instance.name}'.",
            module="Inventory – Categories",
            status="Success",
        )
        return Response({"success": True, "message": "Category updated successfully.", "data": serializer.data})

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name

        if instance.items.exists():
            return Response(
                {
                    "success": False,
                    "message": f"Cannot delete category '{name}' because it contains {instance.items.count()} inventory item(s). Reassign or delete those items first.",
                    "errors": {"detail": "Category has active inventory items."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance.delete()
        except ProtectedError as e:
            return Response(
                {
                    "success": False,
                    "message": f"Cannot delete category '{name}' because it is protected.",
                    "errors": {"detail": str(e)},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            request=request,
            action="Delete Inventory Category",
            description=f"Deleted inventory category '{name}'.",
            module="Inventory – Categories",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Category deleted successfully."},
            status=status.HTTP_200_OK,
        )
