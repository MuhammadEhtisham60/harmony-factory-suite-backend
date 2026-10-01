"""
URLs for the YarnIntake module.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import YarnIntakeViewSet

router = DefaultRouter()
router.register(r"yarn-intakes", YarnIntakeViewSet, basename="yarn-intake")

urlpatterns = [path("", include(router.urls))]
