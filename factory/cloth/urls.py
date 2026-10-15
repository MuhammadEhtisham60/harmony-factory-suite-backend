"""
URL configuration for Cloth Production and Inventory module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ClothNameViewSet,
    ClothPatchViewSet,
    RawStockViewSet,
    ClothStockViewSet,
    CleanClothStockViewSet,
    DefectedClothStockViewSet,
)

router = DefaultRouter()
router.register(r"cloth-names", ClothNameViewSet, basename="cloth-name")
router.register(r"cloth-patches", ClothPatchViewSet, basename="cloth-patch")
router.register(r"raw-stock", RawStockViewSet, basename="raw-stock")
router.register(r"cloth-stock", ClothStockViewSet, basename="cloth-stock")
router.register(r"clean-cloth-stock", CleanClothStockViewSet, basename="clean-cloth-stock")
router.register(r"defected-cloth-stock", DefectedClothStockViewSet, basename="defected-cloth-stock")

urlpatterns = [
    path("", include(router.urls)),
]
