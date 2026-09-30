"""
Admin registration for the Supplier module.
"""

from django.contrib import admin
from .models import Supplier, SupplierBankAccount


class SupplierBankAccountInline(admin.TabularInline):
    model = SupplierBankAccount
    extra = 1
    fields = [
        "bank_name",
        "account_title",
        "account_number",
        "iban",
        "branch_name",
        "branch_code",
        "swift_code",
        "is_primary",
    ]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = [
        "supplier_code",
        "supplier_name",
        "company_name",
        "supplier_type",
        "status",
        "phone",
        "contact_person",
        "created_at",
    ]
    list_filter = ["status", "supplier_type"]
    search_fields = ["supplier_name", "supplier_code", "company_name", "phone", "email"]
    readonly_fields = ["supplier_code", "created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["supplier_name"]
    inlines = [SupplierBankAccountInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "supplier_code",
                    "supplier_name",
                    "company_name",
                    "supplier_type",
                    "status",
                    "registration_number",
                )
            },
        ),
        (
            "Contact Details",
            {
                "fields": (
                    "phone",
                    "email",
                    "contact_person",
                    "address",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(SupplierBankAccount)
class SupplierBankAccountAdmin(admin.ModelAdmin):
    list_display = [
        "supplier",
        "bank_name",
        "account_title",
        "account_number",
        "iban",
        "is_primary",
    ]
    list_filter = ["is_primary", "bank_name"]
    search_fields = ["bank_name", "account_number", "iban", "supplier__supplier_name"]
    readonly_fields = ["created_at", "updated_at"]
