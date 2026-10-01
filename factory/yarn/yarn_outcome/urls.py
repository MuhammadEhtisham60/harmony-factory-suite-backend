"""
URLs for the YarnOutcome module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YarnOutcomeViewSet

router = DefaultRouter()
router.register(r"yarn-outcomes", YarnOutcomeViewSet, basename="yarn-outcome")

urlpatterns = [path("", include(router.urls))]
