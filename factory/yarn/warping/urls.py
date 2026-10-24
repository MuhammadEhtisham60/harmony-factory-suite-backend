"""
URLs for the Warping module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WarpingViewSet

router = DefaultRouter()
router.register(r"warpings", WarpingViewSet, basename="warping")

urlpatterns = [path("", include(router.urls))]
