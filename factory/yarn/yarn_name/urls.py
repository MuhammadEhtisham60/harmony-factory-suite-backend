"""
URLs for YarnName.
"""

from rest_framework.routers import DefaultRouter
from .views import YarnNameViewSet

router = DefaultRouter()
router.register(r"yarn-names", YarnNameViewSet, basename="yarn-name")

urlpatterns = router.urls
