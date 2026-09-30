"""
Admin registration for the Customer module.
"""

from django.contrib import admin
from .models import Customer, CustomerBankAccount


class CustomerBankAccountInline(admin.TabularInline):
    model = CustomerBankAccount
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


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        "customer_code",
        "customer_name",
        "company_name",
        "customer_type",
        "status",
        "phone",
        "contact_person",
        "created_at",
    ]
    list_filter = ["status", "customer_type"]
    search_fields = [
        "customer_name",
        "customer_code",
        "company_name",
        "phone",
        "email",
    ]
    readonly_fields = [
        "customer_code",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    ordering = ["customer_name"]
    inlines = [CustomerBankAccountInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "customer_code",
                    "customer_name",
                    "company_name",
                    "customer_type",
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


@admin.register(CustomerBankAccount)
class CustomerBankAccountAdmin(admin.ModelAdmin):
    list_display = [
        "customer",
        "bank_name",
        "account_title",
        "account_number",
        "iban",
        "is_primary",
    ]
    list_filter = ["is_primary", "bank_name"]
    search_fields = [
        "bank_name",
        "account_number",
        "iban",
        "customer__customer_name",
    ]
    readonly_fields = ["created_at", "updated_at"]
