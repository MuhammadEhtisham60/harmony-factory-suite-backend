"""
URLs for the Sizing, SizingOutcome, and SizingBeamAssignment modules.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SizingViewSet, SizingOutcomeViewSet, SizingBeamAssignmentViewSet

router = DefaultRouter()
router.register(r"sizings", SizingViewSet, basename="sizing")
router.register(r"sizing-outcomes", SizingOutcomeViewSet, basename="sizing-outcome")
router.register(r"sizing-beam-assignments", SizingBeamAssignmentViewSet, basename="sizing-beam-assignment")

urlpatterns = [path("", include(router.urls))]
