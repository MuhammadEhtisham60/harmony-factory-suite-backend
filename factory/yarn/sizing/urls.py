"""
URLs for the Sizing module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SizingViewSet

router = DefaultRouter()
router.register(r"sizings", SizingViewSet, basename="sizing")

urlpatterns = [path("", include(router.urls))]
