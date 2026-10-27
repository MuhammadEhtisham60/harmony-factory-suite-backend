"""
Filters for Bank Accounts and Bank Transactions.
"""

import django_filters
from django.db import models
from .models import BankAccount, BankTransaction


class BankAccountFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    bank_name = django_filters.CharFilter(field_name="bank_name", lookup_expr="icontains")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    account_type = django_filters.CharFilter(field_name="account_type", lookup_expr="iexact")
    currency = django_filters.CharFilter(field_name="currency", lookup_expr="iexact")

    class Meta:
        model = BankAccount
        fields = [
            "search",
            "bank_name",
            "status",
            "account_type",
            "currency",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            models.Q(bank_name__icontains=val)
            | models.Q(account_title__icontains=val)
            | models.Q(account_number__icontains=val)
            | models.Q(iban__icontains=val)
            | models.Q(branch_name__icontains=val)
        )


class BankTransactionFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    account = django_filters.NumberFilter(field_name="account_id")
    transaction_type = django_filters.CharFilter(method="filter_transaction_type")
    payment_method = django_filters.CharFilter(field_name="payment_method", lookup_expr="iexact")
    party_name = django_filters.CharFilter(field_name="party_name", lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = BankTransaction
        fields = [
            "search",
            "account",
            "transaction_type",
            "payment_method",
            "party_name",
            "date_from",
            "date_to",
            "amount_min",
            "amount_max",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            models.Q(reference_number__icontains=val)
            | models.Q(party_name__icontains=val)
            | models.Q(description__icontains=val)
            | models.Q(account__bank_name__icontains=val)
            | models.Q(account__account_title__icontains=val)
            | models.Q(account__account_number__icontains=val)
        )

    def filter_transaction_type(self, queryset, name, value):
        if not value or str(value).lower() in ("all", "none", ""):
            return queryset
        return queryset.filter(transaction_type__iexact=str(value).strip())
