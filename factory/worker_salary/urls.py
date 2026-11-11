"""
URLs for Power Loom Worker Salary & Attendance module.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    WorkerViewSet,
    WorkerAttendanceViewSet,
    PowerLoomSalaryPeriodViewSet,
    WorkerAdvanceViewSet,
    WorkerSalaryPaymentViewSet,
    WorkerSalaryLedgerViewSet,
)

router = DefaultRouter()
router.register(r"workers", WorkerViewSet, basename="worker")
router.register(r"worker-attendance", WorkerAttendanceViewSet, basename="worker-attendance")
router.register(r"power-loom-salary", PowerLoomSalaryPeriodViewSet, basename="power-loom-salary")
router.register(r"worker-advances", WorkerAdvanceViewSet, basename="worker-advance")
router.register(r"worker-payments", WorkerSalaryPaymentViewSet, basename="worker-payment")
router.register(r"worker-salary-ledger", WorkerSalaryLedgerViewSet, basename="worker-salary-ledger")

urlpatterns = [
    path("", include(router.urls)),
]

