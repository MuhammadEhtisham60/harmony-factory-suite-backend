"""
Admin registrations for Power Loom Worker Salary & Attendance module.
"""

from django.contrib import admin
from .models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ["worker_code", "name", "loom_type", "daily_wage_rate", "preferred_payment_cycle", "current_balance", "status"]
    search_fields = ["name", "worker_code", "cnic", "phone"]
    list_filter = ["loom_type", "status", "preferred_payment_cycle"]


@admin.register(WorkerAttendance)
class WorkerAttendanceAdmin(admin.ModelAdmin):
    list_display = ["worker", "date", "status", "daily_wage_rate", "earned_amount", "is_salary_processed"]
    search_fields = ["worker__name", "worker__worker_code"]
    list_filter = ["status", "is_salary_processed", "date"]


@admin.register(PowerLoomSalaryPeriod)
class PowerLoomSalaryPeriodAdmin(admin.ModelAdmin):
    list_display = ["calculation_number", "worker_name", "start_date", "end_date", "payment_cycle", "total_earned_salary", "net_payable_balance", "payment_status"]
    search_fields = ["calculation_number", "worker_name", "worker__worker_code"]
    list_filter = ["payment_cycle", "payment_status"]


@admin.register(WorkerAdvance)
class WorkerAdvanceAdmin(admin.ModelAdmin):
    list_display = ["advance_number", "worker", "advance_date", "amount", "remaining_advance", "status", "payment_method"]
    search_fields = ["advance_number", "worker__name"]
    list_filter = ["status", "payment_method"]


@admin.register(WorkerSalaryPayment)
class WorkerSalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ["payment_number", "worker", "payment_date", "amount", "payment_method", "salary_period"]
    search_fields = ["payment_number", "worker__name", "reference_number"]
    list_filter = ["payment_method"]


@admin.register(WorkerSalaryLedger)
class WorkerSalaryLedgerAdmin(admin.ModelAdmin):
    list_display = ["entry_number", "worker_name", "date", "entry_type", "daily_earned_amount", "advance_amount", "payment_amount", "running_balance"]
    search_fields = ["entry_number", "worker_name", "reference_id"]
    list_filter = ["entry_type", "payment_cycle", "payment_status"]
