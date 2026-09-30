"""
URLs for the Beam module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BeamViewSet

router = DefaultRouter()
router.register(r"beams", BeamViewSet, basename="beam")

urlpatterns = [
    path("", include(router.urls)),
]
