"""
Django Filters for Worker Salary & Attendance module.
"""

import django_filters
from django.db.models import Q
from .models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)


class WorkerFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    loom_type = django_filters.CharFilter(lookup_expr="iexact")
    status = django_filters.CharFilter(lookup_expr="iexact")
    preferred_payment_cycle = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Worker
        fields = ["loom_type", "status", "preferred_payment_cycle"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(worker_code__icontains=value)
            | Q(cnic__icontains=value)
            | Q(phone__icontains=value)
            | Q(designation__icontains=value)
        )


class WorkerAttendanceFilter(django_filters.FilterSet):
    worker = django_filters.NumberFilter(field_name="worker_id")
    date = django_filters.DateFilter()
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    status = django_filters.CharFilter(lookup_expr="iexact")
    is_salary_processed = django_filters.BooleanFilter()

    class Meta:
        model = WorkerAttendance
        fields = ["worker", "date", "status", "is_salary_processed"]


class PowerLoomSalaryPeriodFilter(django_filters.FilterSet):
    worker = django_filters.NumberFilter(field_name="worker_id")
    payment_cycle = django_filters.CharFilter(lookup_expr="iexact")
    payment_status = django_filters.CharFilter(lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = PowerLoomSalaryPeriod
        fields = ["worker", "payment_cycle", "payment_status"]


class WorkerAdvanceFilter(django_filters.FilterSet):
    worker = django_filters.NumberFilter(field_name="worker_id")
    status = django_filters.CharFilter(lookup_expr="iexact")
    payment_method = django_filters.CharFilter(lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="advance_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="advance_date", lookup_expr="lte")

    class Meta:
        model = WorkerAdvance
        fields = ["worker", "status", "payment_method"]


class WorkerSalaryPaymentFilter(django_filters.FilterSet):
    worker = django_filters.NumberFilter(field_name="worker_id")
    salary_period = django_filters.NumberFilter(field_name="salary_period_id")
    payment_method = django_filters.CharFilter(lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")

    class Meta:
        model = WorkerSalaryPayment
        fields = ["worker", "salary_period", "payment_method"]


class WorkerSalaryLedgerFilter(django_filters.FilterSet):
    worker = django_filters.NumberFilter(field_name="worker_id")
    worker_id = django_filters.NumberFilter(field_name="worker_id")
    payment_cycle = django_filters.CharFilter(lookup_expr="iexact")
    payment_status = django_filters.CharFilter(lookup_expr="iexact")
    entry_type = django_filters.CharFilter(lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = WorkerSalaryLedger
        fields = ["worker", "worker_id", "payment_cycle", "payment_status", "entry_type"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(worker__name__icontains=value)
            | Q(worker__worker_code__icontains=value)
            | Q(worker_name__icontains=value)
            | Q(reference_id__icontains=value)
            | Q(description__icontains=value)
        )

