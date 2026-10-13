"""
URLs for YarnCount.
"""

from rest_framework.routers import DefaultRouter
from .views import YarnCountViewSet

router = DefaultRouter()
router.register(r"yarn-counts", YarnCountViewSet, basename="yarn-count")

urlpatterns = router.urls
