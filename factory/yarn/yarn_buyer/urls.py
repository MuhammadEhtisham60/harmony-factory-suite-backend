"""
URLs for the YarnBuyer module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YarnBuyerViewSet

router = DefaultRouter()
router.register(r"yarn-buyers", YarnBuyerViewSet, basename="yarn-buyer")

urlpatterns = [path("", include(router.urls))]
