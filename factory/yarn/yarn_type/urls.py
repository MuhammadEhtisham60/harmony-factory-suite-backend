"""
URLs for YarnType.
"""

from rest_framework.routers import DefaultRouter
from .views import YarnTypeViewSet

router = DefaultRouter()
router.register(r"yarn-types", YarnTypeViewSet, basename="yarn-type")

urlpatterns = router.urls
