"""
Serializers for Power Loom Worker Salary & Attendance module.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.bank_account.models import BankAccount
from .models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)


class WorkerSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Worker
        fields = [
            "id",
            "worker_code",
            "name",
            "cnic",
            "phone",
            "photo",
            "loom_type",
            "daily_wage_rate",
            "per_meter_rate",
            "preferred_payment_cycle",
            "designation",
            "status",
            "joining_date",
            "address",
            "emergency_contact",
            "total_earned_amount",
            "total_advance_amount",
            "total_paid_amount",
            "current_balance",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "worker_code",
            "total_earned_amount",
            "total_advance_amount",
            "total_paid_amount",
            "current_balance",
            "created_at",
            "updated_at",
        ]


class WorkerAttendanceSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.name", read_only=True)
    worker_code = serializers.CharField(source="worker.worker_code", read_only=True)
    loom_type = serializers.CharField(source="worker.loom_type", read_only=True)

    class Meta:
        model = WorkerAttendance
        fields = [
            "id",
            "worker",
            "worker_name",
            "worker_code",
            "loom_type",
            "date",
            "status",
            "daily_wage_rate",
            "per_meter_rate",
            "meters_produced",
            "wage_multiplier",
            "earned_amount",
            "is_salary_processed",
            "salary_period",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "wage_multiplier",
            "earned_amount",
            "is_salary_processed",
            "salary_period",
            "created_at",
            "updated_at",
        ]


class BulkAttendanceCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    attendances = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of {worker_id, status, meters_produced, notes}",
    )


class SalaryCalculationPreviewRequestSerializer(serializers.Serializer):
    worker = serializers.IntegerField()
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    payment_cycle = serializers.ChoiceField(
        choices=PowerLoomSalaryPeriod.PaymentCycleChoices.choices,
        default=PowerLoomSalaryPeriod.PaymentCycleChoices.BI_WEEKLY,
        required=False,
    )
    total_working_days = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    total_meters_produced = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    overtime_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False
    )
    other_earnings = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False
    )
    other_deductions = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False
    )
    advance_payments = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )


class WorkerSalaryPaymentSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.name", read_only=True)
    worker_code = serializers.CharField(source="worker.worker_code", read_only=True)
    salary_calculation_number = serializers.CharField(
        source="salary_period.calculation_number", read_only=True, default=""
    )
    bank_name = serializers.CharField(
        source="bank_account.bank_name", read_only=True, default=""
    )

    class Meta:
        model = WorkerSalaryPayment
        fields = [
            "id",
            "payment_number",
            "worker",
            "worker_name",
            "worker_code",
            "salary_period",
            "salary_calculation_number",
            "payment_date",
            "amount",
            "payment_method",
            "bank_account",
            "bank_name",
            "bank_transaction",
            "reference_number",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "payment_number",
            "bank_transaction",
            "created_at",
        ]


class WorkerAdvanceSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.name", read_only=True)
    worker_code = serializers.CharField(source="worker.worker_code", read_only=True)
    bank_name = serializers.CharField(
        source="bank_account.bank_name", read_only=True, default=""
    )

    class Meta:
        model = WorkerAdvance
        fields = [
            "id",
            "advance_number",
            "worker",
            "worker_name",
            "worker_code",
            "advance_date",
            "amount",
            "amount_deducted",
            "remaining_advance",
            "payment_method",
            "bank_account",
            "bank_name",
            "bank_transaction",
            "status",
            "salary_period",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "advance_number",
            "amount_deducted",
            "remaining_advance",
            "status",
            "bank_transaction",
            "created_at",
        ]


class PowerLoomSalaryPeriodSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.name", read_only=True)
    worker_code = serializers.CharField(source="worker.worker_code", read_only=True)
    payments = WorkerSalaryPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = PowerLoomSalaryPeriod
        fields = [
            "id",
            "calculation_number",
            "worker",
            "worker_name",
            "worker_code",
            "loom_type",
            "daily_wage_rate",
            "per_meter_rate",
            "total_meters_produced",
            "start_date",
            "end_date",
            "payment_cycle",
            "total_working_days",
            "present_days",
            "half_days",
            "absent_days",
            "leave_days",
            "base_earned_salary",
            "overtime_amount",
            "other_earnings",
            "total_earned_salary",
            "advance_payments",
            "other_deductions",
            "total_paid_amount",
            "net_payable_balance",
            "payment_status",
            "notes",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "calculation_number",
            "worker_name",
            "worker_code",
            "base_earned_salary",
            "total_earned_salary",
            "total_paid_amount",
            "net_payable_balance",
            "payment_status",
            "created_at",
            "updated_at",
        ]


class WorkerSalaryLedgerSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.name", read_only=True)
    worker_code = serializers.CharField(source="worker.worker_code", read_only=True)
    loom_type = serializers.CharField(source="worker.loom_type", read_only=True)

    class Meta:
        model = WorkerSalaryLedger
        fields = [
            "id",
            "entry_number",
            "worker",
            "worker_name",
            "worker_code",
            "loom_type",
            "date",
            "entry_type",
            "daily_wage_rate",
            "per_meter_rate",
            "meters_produced",
            "attendance_status",
            "daily_earned_amount",
            "advance_amount",
            "payment_amount",
            "deduction_amount",
            "running_balance",
            "payment_cycle",
            "payment_status",
            "reference_id",
            "description",
            "salary_period",
            "attendance_record",
            "advance_record",
            "payment_record",
            "created_at",
        ]
        read_only_fields = fields

