"""
URLs for the YarnStock module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YarnStockViewSet

router = DefaultRouter()
router.register(r"yarn-stocks", YarnStockViewSet, basename="yarn-stock")

urlpatterns = [path("", include(router.urls))]
