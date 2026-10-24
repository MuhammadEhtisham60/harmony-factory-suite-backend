"""
URLs for the Warping module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WarpingViewSet, WarpingOutcomeViewSet
from .ledger_views import WarpingLedgerViewSet

router = DefaultRouter()
router.register(r"warpings", WarpingViewSet, basename="warping")
router.register(r"warping-outcomes", WarpingOutcomeViewSet, basename="warping-outcome")
router.register(r"warping_outcomes", WarpingOutcomeViewSet, basename="warping_outcome")
router.register(r"warping-ledger", WarpingLedgerViewSet, basename="warping-ledger")

urlpatterns = [path("", include(router.urls))]
