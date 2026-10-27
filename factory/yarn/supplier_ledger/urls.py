"""
URLs for the Yarn Supplier Ledger module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YarnSupplierLedgerViewSet

router = DefaultRouter()
router.register(r"yarn-supplier-ledger", YarnSupplierLedgerViewSet, basename="yarn-supplier-ledger")
router.register(r"supplier-ledger", YarnSupplierLedgerViewSet, basename="supplier-ledger")

urlpatterns = [path("", include(router.urls))]
