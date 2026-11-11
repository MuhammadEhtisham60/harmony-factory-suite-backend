"""
URLs for the Inventory management module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from factory.inventory.category.views import InventoryCategoryViewSet
from factory.inventory.unit.views import InventoryUnitViewSet
from factory.inventory.item.views import InventoryItemViewSet
from factory.inventory.purchase.views import InventoryPurchaseViewSet
from factory.inventory.transaction.views import InventoryTransactionViewSet
from factory.inventory.ledger.views import InventoryLedgerListView

router = DefaultRouter()
router.register(r"categories", InventoryCategoryViewSet, basename="inventory-category")
router.register(r"units", InventoryUnitViewSet, basename="inventory-unit")
router.register(r"items", InventoryItemViewSet, basename="inventory-item")
router.register(r"purchases", InventoryPurchaseViewSet, basename="inventory-purchase")
router.register(r"transactions", InventoryTransactionViewSet, basename="inventory-transaction")

urlpatterns = [
    path("ledger/", InventoryLedgerListView.as_view(), name="inventory-ledger-list"),
    path("stats/", InventoryItemViewSet.as_view({"get": "stats"}), name="inventory-global-stats"),
    path("", include(router.urls)),
]

