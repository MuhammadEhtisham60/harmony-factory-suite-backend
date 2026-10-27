"""
URLs for the B-Grade Yarn module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BGradeYarnViewSet

router = DefaultRouter()
router.register(r"b-grade-yarn", BGradeYarnViewSet, basename="b-grade-yarn")

urlpatterns = [path("", include(router.urls))]
