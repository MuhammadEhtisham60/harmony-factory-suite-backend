"""
Admin configuration for Inventory models.
"""

from django.contrib import admin
from factory.inventory.category.models import InventoryCategory
from factory.inventory.unit.models import InventoryUnit
from factory.inventory.item.models import InventoryItem
from factory.inventory.purchase.models import InventoryPurchase, InventoryPurchaseItem
from factory.inventory.transaction.models import InventoryTransaction
from factory.inventory.ledger.models import InventoryLedger


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "is_active", "created_at"]
    search_fields = ["name", "description"]
    list_filter = ["is_active"]


@admin.register(InventoryUnit)
class InventoryUnitAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "abbreviation", "is_active", "created_at"]
    search_fields = ["name", "abbreviation"]
    list_filter = ["is_active"]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "item_code",
        "item_name",
        "category",
        "unit",
        "current_stock",
        "minimum_stock_level",
        "status",
        "created_at",
    ]
    search_fields = ["item_code", "item_name", "description", "storage_location"]
    list_filter = ["status", "category", "unit"]
    readonly_fields = ["item_code", "current_stock", "created_at", "updated_at"]


class InventoryPurchaseItemInline(admin.TabularInline):
    model = InventoryPurchaseItem
    extra = 1


@admin.register(InventoryPurchase)
class InventoryPurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "purchase_number",
        "supplier",
        "purchase_date",
        "total_amount",
        "status",
        "created_at",
    ]
    search_fields = ["purchase_number", "reference_number", "supplier__supplier_name"]
    list_filter = ["status", "purchase_date"]
    inlines = [InventoryPurchaseItemInline]


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "transaction_number",
        "transaction_date",
        "inventory_item",
        "transaction_type",
        "quantity",
        "issued_to",
        "created_at",
    ]
    search_fields = ["transaction_number", "inventory_item__item_name", "issued_to", "notes"]
    list_filter = ["transaction_type", "transaction_date"]
    readonly_fields = ["transaction_number", "created_at"]


@admin.register(InventoryLedger)
class InventoryLedgerAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "transaction_number",
        "transaction_date",
        "inventory_item",
        "transaction_type",
        "quantity_in",
        "quantity_out",
        "running_balance",
        "supplier",
        "created_at",
    ]
    search_fields = [
        "transaction_number",
        "inventory_item__item_name",
        "inventory_item__item_code",
        "notes",
    ]
    list_filter = ["transaction_type", "transaction_date"]
    readonly_fields = [
        "inventory_item",
        "transaction_date",
        "transaction_number",
        "transaction_type",
        "quantity_in",
        "quantity_out",
        "running_balance",
        "reference_id",
        "reference_type",
        "supplier",
        "notes",
        "created_at",
        "created_by",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

