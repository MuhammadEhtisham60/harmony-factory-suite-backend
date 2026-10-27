from django.contrib import admin
from .models import BankAccount, BankTransaction


class BankTransactionInline(admin.TabularInline):
    model = BankTransaction
    extra = 0
    fields = ["date", "transaction_type", "amount", "payment_method", "reference_number", "party_name", "running_balance"]
    readonly_fields = ["running_balance"]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = [
        "bank_name",
        "account_title",
        "account_number",
        "account_type",
        "opening_balance",
        "current_balance",
        "total_credit",
        "total_debit",
        "status",
        "created_at",
    ]
    list_filter = ["status", "account_type", "currency", "bank_name"]
    search_fields = ["bank_name", "account_title", "account_number", "iban"]
    readonly_fields = ["current_balance", "total_credit", "total_debit", "created_at", "updated_at"]
    inlines = [BankTransactionInline]


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "account",
        "transaction_type",
        "amount",
        "date",
        "payment_method",
        "party_name",
        "reference_number",
        "running_balance",
        "created_at",
    ]
    list_filter = ["transaction_type", "payment_method", "date", "account__bank_name"]
    search_fields = ["reference_number", "party_name", "description", "account__bank_name", "account__account_number"]
    readonly_fields = ["running_balance", "created_at", "updated_at"]
