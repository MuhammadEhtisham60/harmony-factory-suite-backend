"""
Views for Bank Accounts and Bank Transactions.
Provides CRUD and financial statement actions.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import BankAccount, BankTransaction
from .serializers import (
    BankAccountSerializer,
    BankAccountDetailSerializer,
    BankTransactionSerializer,
)
from .filters import BankAccountFilter, BankTransactionFilter


class BankAccountViewSet(ModelViewSet):
    """
    CRUD ModelViewSet for Bank Accounts.

    Endpoints:
        GET    /api/v1/bank-accounts/               – List bank accounts (paginated)
        POST   /api/v1/bank-accounts/               – Create bank account with opening balance
        GET    /api/v1/bank-accounts/{id}/          – Retrieve bank account with recent ledger
        PUT    /api/v1/bank-accounts/{id}/          – Update bank account
        PATCH  /api/v1/bank-accounts/{id}/          – Partial update
        DELETE /api/v1/bank-accounts/{id}/          – Delete bank account
        GET    /api/v1/bank-accounts/summary/       – High-level metrics (total accounts, net balance, credits, debits)
        GET    /api/v1/bank-accounts/{id}/transactions/ – List all transactions of this account
        POST   /api/v1/bank-accounts/{id}/add_transaction/ – Record Credit or Debit directly
    """
    queryset = BankAccount.objects.select_related("created_by", "updated_by").prefetch_related("transactions").all()
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "bank.view",
        "POST": "bank.add",
        "PUT": "bank.edit",
        "PATCH": "bank.edit",
        "DELETE": "bank.delete",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BankAccountFilter
    search_fields = [
        "bank_name",
        "account_title",
        "account_number",
        "iban",
        "branch_name",
        "notes",
    ]
    ordering_fields = [
        "bank_name",
        "account_title",
        "account_number",
        "current_balance",
        "opening_balance",
        "total_credit",
        "total_debit",
        "created_at",
        "opening_date",
    ]
    ordering = ["bank_name", "account_title"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BankAccountDetailSerializer
        return BankAccountSerializer

    def perform_create(self, serializer):
        account = serializer.save()
        log_activity(
            self.request,
            action="CREATE",
            description=f"Created bank account {account.bank_name} - {account.account_title} ({account.account_number}) with opening balance {account.opening_balance}",
            module="Bank Accounts",
        )

    def perform_update(self, serializer):
        account = serializer.save()
        log_activity(
            self.request,
            action="UPDATE",
            description=f"Updated bank account {account.bank_name} - {account.account_title} ({account.account_number})",
            module="Bank Accounts",
        )

    def perform_destroy(self, instance):
        title = f"{instance.bank_name} - {instance.account_title} ({instance.account_number})"
        super().perform_destroy(instance)
        log_activity(
            self.request,
            action="DELETE",
            description=f"Deleted bank account {title}",
            module="Bank Accounts",
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        Returns consolidated statistics across all bank accounts.
        """
        accounts = BankAccount.objects.all()
        total_accounts = accounts.count()
        active_accounts = accounts.filter(status=BankAccount.Status.ACTIVE).count()

        aggregates = accounts.aggregate(
            sum_opening=Sum("opening_balance"),
            sum_balance=Sum("current_balance"),
            sum_credits=Sum("total_credit"),
            sum_debits=Sum("total_debit"),
        )

        return Response({
            "totalAccounts": total_accounts,
            "activeAccounts": active_accounts,
            "totalOpeningBalance": aggregates["sum_opening"] or Decimal("0.00"),
            "totalCurrentBalance": aggregates["sum_balance"] or Decimal("0.00"),
            "totalCredits": aggregates["sum_credits"] or Decimal("0.00"),
            "totalDebits": aggregates["sum_debits"] or Decimal("0.00"),
        })

    @action(detail=True, methods=["get"], url_path="transactions")
    def transactions(self, request, pk=None):
        """
        Retrieves paginated transactions for this specific bank account.
        """
        account = self.get_object()
        txs = account.transactions.select_related("account", "created_by", "updated_by").all()

        # Apply transaction filtering
        filterset = BankTransactionFilter(request.GET, queryset=txs)
        if filterset.is_valid():
            txs = filterset.qs

        page = self.paginate_queryset(txs)
        if page is not None:
            serializer = BankTransactionSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = BankTransactionSerializer(txs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="add_transaction")
    def add_transaction(self, request, pk=None):
        """
        Quick endpoint to record a transaction (Credit/Debit) directly for this account.
        """
        account = self.get_object()
        data = request.data.copy()
        data["account"] = account.id

        serializer = BankTransactionSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tx = serializer.save()

        log_activity(
            request,
            action="CREATE",
            description=f"Recorded {tx.transaction_type} of {tx.amount} in {account.bank_name} ({account.account_number})",
            module="Bank Transactions",
        )

        # Return updated account details and new transaction
        account.refresh_from_db()
        return Response(
            {
                "transaction": serializer.data,
                "account": BankAccountSerializer(account, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BankTransactionViewSet(ModelViewSet):
    """
    CRUD ModelViewSet for Bank Transactions.

    Endpoints:
        GET    /api/v1/bank-transactions/      – List all transactions
        POST   /api/v1/bank-transactions/      – Record Credit/Debit transaction
        GET    /api/v1/bank-transactions/{id}/ – Retrieve transaction details
        PUT    /api/v1/bank-transactions/{id}/ – Update transaction
        PATCH  /api/v1/bank-transactions/{id}/ – Partial update
        DELETE /api/v1/bank-transactions/{id}/ – Delete transaction & recalculate balance
    """
    queryset = BankTransaction.objects.select_related("account", "created_by", "updated_by").all()
    serializer_class = BankTransactionSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "bank.view",
        "POST": "bank.transaction",
        "PUT": "bank.transaction",
        "PATCH": "bank.transaction",
        "DELETE": "bank.transaction",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BankTransactionFilter
    search_fields = [
        "reference_number",
        "party_name",
        "description",
        "account__bank_name",
        "account__account_title",
        "account__account_number",
    ]
    ordering_fields = [
        "date",
        "amount",
        "transaction_type",
        "created_at",
        "running_balance",
    ]
    ordering = ["-date", "-created_at"]

    def perform_create(self, serializer):
        tx = serializer.save()
        log_activity(
            self.request,
            action="CREATE",
            description=f"Recorded {tx.transaction_type} of {tx.amount} for {tx.account.bank_name} ({tx.account.account_number})",
            module="Bank Transactions",
        )

    def perform_update(self, serializer):
        tx = serializer.save()
        log_activity(
            self.request,
            action="UPDATE",
            description=f"Updated {tx.transaction_type} of {tx.amount} for {tx.account.bank_name} ({tx.account.account_number})",
            module="Bank Transactions",
        )

    def perform_destroy(self, instance):
        desc = f"Deleted {instance.transaction_type} of {instance.amount} from {instance.account.bank_name}"
        super().perform_destroy(instance)
        log_activity(
            self.request,
            action="DELETE",
            description=desc,
            module="Bank Transactions",
        )
