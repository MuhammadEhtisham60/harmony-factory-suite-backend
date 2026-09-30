"""
URLs for the Loom module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LoomViewSet

router = DefaultRouter()
router.register(r"looms", LoomViewSet, basename="loom")

urlpatterns = [
    path("", include(router.urls)),
]
