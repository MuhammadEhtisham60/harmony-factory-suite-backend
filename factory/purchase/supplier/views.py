"""
Views for the Supplier module – full CRUD via ModelViewSet.
Bank accounts are handled inline through the serializer.
"""

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

from .models import Supplier
from .serializers import SupplierListSerializer, SupplierDetailSerializer
from .filters import SupplierFilter


class SupplierViewSet(ModelViewSet):
    """
    ModelViewSet for Supplier CRUD operations.

    Bank accounts are handled as a nested writable list via the serializer.
    Simply include `bankAccounts` in the request body when creating or updating.

    Endpoints (router-generated):
        GET    /suppliers/            – list   (paginated, filterable)
        POST   /suppliers/            – create (with optional bankAccounts[])
        GET    /suppliers/{id}/       – retrieve (includes bankAccounts[])
        PUT    /suppliers/{id}/       – full update  (reconciles bankAccounts[])
        PATCH  /suppliers/{id}/       – partial update
        DELETE /suppliers/{id}/       – destroy (cascades to bank accounts)
        GET    /suppliers/stats/      – aggregate counts by status & type
        GET    /suppliers/choices/    – available choices for dropdowns
    """

    queryset = (
        Supplier.objects
        .select_related("created_by", "updated_by")
        .prefetch_related("bank_accounts")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SupplierFilter
    search_fields = [
        "supplier_name",
        "supplier_code",
        "company_name",
        "phone",
        "email",
        "contact_person",
    ]
    ordering_fields = [
        "supplier_name",
        "supplier_code",
        "company_name",
        "status",
        "supplier_type",
        "created_at",
        "updated_at",
    ]
    ordering = ["supplier_name"]

    # Permission map for RBAC
    permission_map = {
        "GET": "suppliers.view",
        "POST": "suppliers.add",
        "PUT": "suppliers.change",
        "PATCH": "suppliers.change",
        "DELETE": "suppliers.delete",
    }

    # ------------------------------------------------------------------ #
    # Serializer selection
    # ------------------------------------------------------------------ #

    def get_serializer_class(self):
        if self.action == "list":
            return SupplierListSerializer
        return SupplierDetailSerializer

    # ------------------------------------------------------------------ #
    # Standard action overrides
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        serializer = SupplierDetailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Supplier",
            description=(
                f"Created supplier '{instance.supplier_name}' ({instance.supplier_code})"
                f" with {instance.bank_accounts.count()} bank account(s)."
            ),
            module="Purchase – Suppliers",
            status="Success",
        )

        # Re-serialize with prefetch so bank accounts are returned
        out = SupplierDetailSerializer(
            Supplier.objects
            .select_related("created_by", "updated_by")
            .prefetch_related("bank_accounts")
            .get(pk=instance.pk),
            context={"request": request},
        )
        return Response(
            {"success": True, "message": "Supplier created successfully.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SupplierDetailSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SupplierDetailSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Supplier",
            description=(
                f"Updated supplier '{updated.supplier_name}' ({updated.supplier_code})"
                f" – {updated.bank_accounts.count()} bank account(s) on record."
            ),
            module="Purchase – Suppliers",
            status="Success",
        )

        # Re-fetch with prefetch for fresh nested data
        out = SupplierDetailSerializer(
            Supplier.objects
            .select_related("created_by", "updated_by")
            .prefetch_related("bank_accounts")
            .get(pk=updated.pk),
            context={"request": request},
        )
        return Response(
            {"success": True, "message": "Supplier updated successfully.", "data": out.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        supplier_code = instance.supplier_code
        supplier_name = instance.supplier_name
        bank_count = instance.bank_accounts.count()
        # CASCADE on FK deletes bank accounts automatically
        instance.delete()

        log_activity(
            request=request,
            action="Delete Supplier",
            description=(
                f"Deleted supplier '{supplier_name}' ({supplier_code})"
                f" and {bank_count} associated bank account(s)."
            ),
            module="Purchase – Suppliers",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Supplier deleted successfully."},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------ #
    # Extra custom actions
    # ------------------------------------------------------------------ #

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        Returns aggregate counts:
            - totalSuppliers
            - byStatus  : {Active: n, Inactive: n, Blocked: n}
            - byType    : {Yarn: n, ...}
        """
        qs = self.filter_queryset(self.get_queryset())

        by_status = {
            v: qs.filter(status=v).count()
            for v, _ in Supplier.StatusChoices.choices
        }
        by_type = {
            v: qs.filter(supplier_type=v).count()
            for v, _ in Supplier.SupplierType.choices
        }

        return Response({
            "success": True,
            "data": {
                "totalSuppliers": qs.count(),
                "byStatus": by_status,
                "byType": by_type,
            },
        })

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """
        Returns dropdown option lists for supplier_type and status.
        """
        return Response({
            "success": True,
            "data": {
                "supplierTypes": [
                    {"value": v, "label": l}
                    for v, l in Supplier.SupplierType.choices
                ],
                "statusChoices": [
                    {"value": v, "label": l}
                    for v, l in Supplier.StatusChoices.choices
                ],
            },
        })
