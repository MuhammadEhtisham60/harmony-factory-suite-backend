"""
URLs for the Customer Cloth Ledger and Cloth Sales module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerClothLedgerViewSet, ClothSaleViewSet

router = DefaultRouter()
router.register(r"customer-ledger", CustomerClothLedgerViewSet, basename="customer-ledger")
router.register(r"customer-cloth-ledger", CustomerClothLedgerViewSet, basename="customer-cloth-ledger")
router.register(r"cloth-sales", ClothSaleViewSet, basename="cloth-sale")

urlpatterns = [path("", include(router.urls))]
