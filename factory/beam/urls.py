"""
URLs for the Beam module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BeamViewSet, BeamLoadingViewSet, ProductionViewSet

router = DefaultRouter()
router.register(r"beams", BeamViewSet, basename="beam")
router.register(r"beam-loadings", BeamLoadingViewSet, basename="beam-loading")
router.register(r"productions", ProductionViewSet, basename="production")

urlpatterns = [
    path("", include(router.urls)),
]

