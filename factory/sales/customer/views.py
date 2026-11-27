"""
Views for the Customer module – full CRUD via ModelViewSet.
Bank accounts are handled inline through the serializer.
"""

from decimal import Decimal

from django.db.models.deletion import ProtectedError

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

from .models import Customer
from .serializers import CustomerListSerializer, CustomerDetailSerializer
from .filters import CustomerFilter


class CustomerViewSet(ModelViewSet):
    """
    ModelViewSet for Customer CRUD operations.

    Bank accounts are handled as a nested writable list via the serializer.
    Include `bankAccounts` in the request body when creating or updating.

    Endpoints (router-generated):
        GET    /customers/            – list   (paginated, filterable)
        POST   /customers/            – create (with optional bankAccounts[])
        GET    /customers/{id}/       – retrieve (includes bankAccounts[])
        PUT    /customers/{id}/       – full update  (reconciles bankAccounts[])
        PATCH  /customers/{id}/       – partial update
        DELETE /customers/{id}/       – destroy (cascades to bank accounts)
        GET    /customers/stats/      – aggregate counts by status & type
        GET    /customers/choices/    – available dropdown choices
    """

    queryset = (
        Customer.objects
        .select_related("created_by", "updated_by")
        .prefetch_related("bank_accounts")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CustomerFilter
    search_fields = [
        "customer_name",
        "customer_code",
        "company_name",
        "phone",
        "email",
        "contact_person",
    ]
    ordering_fields = [
        "customer_code",
        "company_name",
        "status",
        "customer_type",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    # RBAC permission map
    permission_map = {
        "GET": "customers.view",
        "POST": "customers.add",
        "PUT": "customers.change",
        "PATCH": "customers.change",
        "DELETE": "customers.delete",
    }

    # ------------------------------------------------------------------ #
    # Serializer selection
    # ------------------------------------------------------------------ #

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        return CustomerDetailSerializer

    # ------------------------------------------------------------------ #
    # CRUD overrides – consistent response shape + audit logging
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        serializer = CustomerDetailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Customer",
            description=(
                f"Created customer '{instance.customer_name}' ({instance.customer_code})"
                f" with {instance.bank_accounts.count()} bank account(s)."
            ),
            module="Sales – Customers",
            status="Success",
        )

        out = CustomerDetailSerializer(
            Customer.objects
            .select_related("created_by", "updated_by")
            .prefetch_related("bank_accounts")
            .get(pk=instance.pk),
            context={"request": request},
        )
        return Response(
            {
                "success": True,
                "message": "Customer created successfully.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = CustomerDetailSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def _get_uncleared_dues_error(self, instance, action_label="perform this action on"):
        from factory.sales.customer_ledger.ledger import (
            build_customer_cloth_ledger,
            exact_str,
        )

        customer_ledger = build_customer_cloth_ledger(instance)
        ledger_balance = (
            customer_ledger["summary"].get("total_receivables") or Decimal("0")
        )
        if ledger_balance > Decimal("0"):
            return (
                f"Cannot {action_label} '{instance.customer_name}': "
                f"uncleared ledger receivables of PKR {exact_str(ledger_balance)} remain. "
                f"Please clear all dues first."
            )
        if ledger_balance < Decimal("0"):
            return (
                f"Cannot {action_label} '{instance.customer_name}': "
                f"uncleared ledger payables/credit of PKR {exact_str(abs(ledger_balance))} remain. "
                f"Please settle all dues first."
            )
        return None

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Block status change if customer has uncleared receivables/payables
        new_status = request.data.get("status")
        if new_status is not None and new_status != instance.status:
            dues_err = self._get_uncleared_dues_error(instance, action_label="change status of")
            if dues_err:
                return Response(
                    {"success": False, "message": dues_err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = CustomerDetailSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Customer",
            description=(
                f"Updated customer '{updated.customer_name}' ({updated.customer_code})"
                f" – {updated.bank_accounts.count()} bank account(s) on record."
            ),
            module="Sales – Customers",
            status="Success",
        )

        out = CustomerDetailSerializer(
            Customer.objects
            .select_related("created_by", "updated_by")
            .prefetch_related("bank_accounts")
            .get(pk=updated.pk),
            context={"request": request},
        )
        return Response(
            {
                "success": True,
                "message": "Customer updated successfully.",
                "data": out.data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # 1. Only Inactive customers can be deleted
        if instance.status != Customer.StatusChoices.INACTIVE:
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Only Inactive customers can be deleted. "
                        f"'{instance.customer_name}' is currently '{instance.status}'. "
                        f"Please mark the customer as Inactive first."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Check Customer Cloth Ledger receivables / payables
        from factory.sales.customer_ledger.ledger import (
            build_customer_cloth_ledger,
            exact_str,
        )

        customer_ledger = build_customer_cloth_ledger(instance)
        ledger_balance = (
            customer_ledger["summary"].get("total_receivables") or Decimal("0")
        )
        if ledger_balance > Decimal("0"):
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Cannot delete '{instance.customer_name}': "
                        f"uncleared ledger receivables of PKR {exact_str(ledger_balance)} remain. "
                        f"Please clear all receivables before deleting."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ledger_balance < Decimal("0"):
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Cannot delete '{instance.customer_name}': "
                        f"uncleared ledger payables/credit of PKR {exact_str(abs(ledger_balance))} remain. "
                        f"Please settle all payables before deleting."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_code = instance.customer_code
        customer_name = instance.customer_name
        bank_count = instance.bank_accounts.count()
        try:
            # CASCADE on FK deletes bank accounts automatically
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Cannot delete '{customer_name}' because it has linked "
                        f"transaction history (e.g., cloth sales or payments)."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            request=request,
            action="Delete Customer",
            description=(
                f"Deleted customer '{customer_name}' ({customer_code})"
                f" and {bank_count} associated bank account(s)."
            ),
            module="Sales – Customers",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Customer deleted successfully."},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------ #
    # Custom actions
    # ------------------------------------------------------------------ #

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        Returns aggregate counts:
            totalCustomers
            byStatus   : {Active: n, Inactive: n, Blocked: n}
            byType     : {Wholesaler: n, Retailer: n, ...}
        """
        qs = self.filter_queryset(self.get_queryset())

        by_status = {
            v: qs.filter(status=v).count()
            for v, _ in Customer.StatusChoices.choices
        }
        by_type = {
            v: qs.filter(customer_type=v).count()
            for v, _ in Customer.CustomerType.choices
        }

        return Response(
            {
                "success": True,
                "data": {
                    "totalCustomers": qs.count(),
                    "byStatus": by_status,
                    "byType": by_type,
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """
        Returns dropdown option lists for customer_type and status.
        """
        return Response(
            {
                "success": True,
                "data": {
                    "customerTypes": [
                        {"value": v, "label": l}
                        for v, l in Customer.CustomerType.choices
                    ],
                    "statusChoices": [
                        {"value": v, "label": l}
                        for v, l in Customer.StatusChoices.choices
                    ],
                },
            }
        )
