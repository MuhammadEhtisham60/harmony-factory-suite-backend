"""
Views and API Endpoints for Power Loom Worker Salary & Attendance module.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity
from factory.bank_account.models import BankAccount

from .models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)
from .serializers import (
    WorkerSerializer,
    WorkerAttendanceSerializer,
    BulkAttendanceCreateSerializer,
    PowerLoomSalaryPeriodSerializer,
    SalaryCalculationPreviewRequestSerializer,
    WorkerAdvanceSerializer,
    WorkerSalaryPaymentSerializer,
    WorkerSalaryLedgerSerializer,
)
from .filters import (
    WorkerFilter,
    WorkerAttendanceFilter,
    PowerLoomSalaryPeriodFilter,
    WorkerAdvanceFilter,
    WorkerSalaryPaymentFilter,
    WorkerSalaryLedgerFilter,
)
from .services import (
    record_daily_attendance,
    calculate_salary_preview,
    finalize_salary_period,
    record_worker_advance,
    record_salary_payment,
    recalculate_worker_ledger,
)


class WorkerViewSet(ModelViewSet):
    """
    CRUD for Workers.
    """
    queryset = Worker.objects.select_related("created_by").all()
    serializer_class = WorkerSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "emp.view",
        "POST": "emp.add",
        "PUT": "emp.edit",
        "PATCH": "emp.edit",
        "DELETE": "emp.delete",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkerFilter
    search_fields = ["name", "worker_code", "cnic", "phone", "designation"]
    ordering_fields = ["id", "worker_code", "name", "daily_wage_rate", "current_balance", "created_at"]
    ordering = ["-id"]

    def perform_create(self, serializer):
        worker = serializer.save(created_by=self.request.user)
        log_activity(
            self.request,
            action="Created Worker",
            description=f"Created worker {worker.name} ({worker.worker_code}) - {worker.loom_type}",
            module="HR & Workforce",
        )

    def perform_update(self, serializer):
        worker = serializer.save()
        log_activity(
            self.request,
            action="Updated Worker",
            description=f"Updated worker {worker.name} ({worker.worker_code}) - {worker.loom_type}",
            module="HR & Workforce",
        )

    def perform_destroy(self, instance):
        worker_name = instance.name
        worker_code = instance.worker_code
        instance.delete()
        log_activity(
            self.request,
            action="Deleted Worker",
            description=f"Deleted worker {worker_name} ({worker_code})",
            module="HR & Workforce",
        )

    @action(detail=True, methods=["post"], url_path="recalculate-ledger")
    def recalculate_ledger(self, request, pk=None):
        worker = self.get_object()
        recalculate_worker_ledger(worker)
        serializer = self.get_serializer(worker)
        return Response(
            {"message": "Worker ledger recalculation completed successfully.", "worker": serializer.data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="ledger")
    def worker_ledger(self, request, pk=None):
        worker = self.get_object()
        entries = WorkerSalaryLedger.objects.filter(worker=worker).order_by("date", "id")
        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = WorkerSalaryLedgerSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = WorkerSalaryLedgerSerializer(entries, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        workers = self.get_queryset()
        total_workers = workers.count()
        active_workers = workers.filter(status="Active").count()
        total_balance_payable = workers.aggregate(total=Sum("current_balance"))["total"] or Decimal("0.00")
        total_earned = workers.aggregate(total=Sum("total_earned_amount"))["total"] or Decimal("0.00")
        total_advances = workers.aggregate(total=Sum("total_advance_amount"))["total"] or Decimal("0.00")
        total_paid = workers.aggregate(total=Sum("total_paid_amount"))["total"] or Decimal("0.00")

        return Response({
            "total_workers": total_workers,
            "active_workers": active_workers,
            "total_balance_payable": str(total_balance_payable),
            "total_earned": str(total_earned),
            "total_advances": str(total_advances),
            "total_paid": str(total_paid),
        })


class WorkerAttendanceViewSet(ModelViewSet):
    """
    Daily Attendance Management.
    """
    queryset = WorkerAttendance.objects.select_related("worker", "created_by").all()
    serializer_class = WorkerAttendanceSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "att.view",
        "POST": "att.mark",
        "PUT": "att.edit",
        "PATCH": "att.edit",
        "DELETE": "att.mark",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkerAttendanceFilter
    search_fields = ["worker__name", "worker__worker_code", "status"]
    ordering_fields = ["date", "id", "worker__name", "earned_amount"]
    ordering = ["-date", "-id"]

    def create(self, request, *args, **kwargs):
        worker_id = request.data.get("worker")
        date = request.data.get("date") or str(timezone.localdate())
        status_val = request.data.get("status", "Present")
        rate = request.data.get("daily_wage_rate")
        m_rate = request.data.get("per_meter_rate")
        meters = request.data.get("meters_produced")
        notes = request.data.get("notes", "")

        try:
            worker = Worker.objects.get(pk=worker_id)
        except Worker.DoesNotExist:
            return Response({"worker": "Worker not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            att = record_daily_attendance(
                worker=worker,
                date=date,
                status=status_val,
                daily_wage_rate=rate,
                per_meter_rate=m_rate,
                meters_produced=meters,
                notes=notes,
                user=request.user,
            )
            serializer = self.get_serializer(att)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="bulk-mark")
    def bulk_mark(self, request):
        serializer = BulkAttendanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        date = serializer.validated_data["date"]
        attendances = serializer.validated_data["attendances"]

        created_count = 0
        errors = []

        for item in attendances:
            worker_id = item.get("worker_id") or item.get("worker")
            status_val = item.get("status", "Present")
            meters = item.get("meters_produced")
            notes = item.get("notes", "")
            try:
                worker = Worker.objects.get(pk=worker_id)
                record_daily_attendance(
                    worker=worker,
                    date=date,
                    status=status_val,
                    meters_produced=meters,
                    notes=notes,
                    user=request.user,
                )
                created_count += 1
            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")

        return Response(
            {
                "message": f"Successfully processed {created_count} attendance records.",
                "date": str(date),
                "created_count": created_count,
                "errors": errors,
            },
            status=status.HTTP_200_OK,
        )


class PowerLoomSalaryPeriodViewSet(ModelViewSet):
    """
    Power Loom & Manual Loom Worker Salary Calculation and Flexible Payment Cycle.
    """
    queryset = PowerLoomSalaryPeriod.objects.select_related("worker", "created_by").prefetch_related("payments").all()
    serializer_class = PowerLoomSalaryPeriodSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "payroll.process",
        "POST": "payroll.process",
        "PUT": "payroll.process",
        "PATCH": "payroll.process",
        "DELETE": "payroll.process",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PowerLoomSalaryPeriodFilter
    search_fields = ["calculation_number", "worker__name", "worker__worker_code", "worker_name"]
    ordering_fields = ["start_date", "end_date", "id", "total_earned_salary", "net_payable_balance"]
    ordering = ["-start_date", "-id"]

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        serializer = SalaryCalculationPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            worker = Worker.objects.get(pk=data["worker"])
        except Worker.DoesNotExist:
            return Response({"worker": "Worker not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            preview_data = calculate_salary_preview(
                worker=worker,
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                payment_cycle=data.get("payment_cycle", "15 Days"),
                overtime_amount=data.get("overtime_amount", Decimal("0.00")),
                other_earnings=data.get("other_earnings", Decimal("0.00")),
                other_deductions=data.get("other_deductions", Decimal("0.00")),
                advance_payments=data.get("advance_payments"),
                total_working_days=data.get("total_working_days"),
                total_meters_produced=data.get("total_meters_produced"),
            )
            return Response(preview_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="finalize")
    def finalize(self, request):
        serializer = SalaryCalculationPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            worker = Worker.objects.get(pk=data["worker"])
        except Worker.DoesNotExist:
            return Response({"worker": "Worker not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            salary_period = finalize_salary_period(
                worker=worker,
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                payment_cycle=data.get("payment_cycle", "15 Days"),
                overtime_amount=data.get("overtime_amount", Decimal("0.00")),
                other_earnings=data.get("other_earnings", Decimal("0.00")),
                other_deductions=data.get("other_deductions", Decimal("0.00")),
                advance_payments=data.get("advance_payments"),
                total_working_days=data.get("total_working_days"),
                total_meters_produced=data.get("total_meters_produced"),
                notes=request.data.get("notes", ""),
                user=request.user,
            )
            resp_serializer = self.get_serializer(salary_period)
            return Response(resp_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="pay")
    def record_period_payment(self, request, pk=None):
        salary_period = self.get_object()
        amount = request.data.get("amount")
        payment_date = request.data.get("payment_date") or str(timezone.localdate())
        payment_method = request.data.get("payment_method", "Cash")
        bank_account_id = request.data.get("bank_account")
        reference_number = request.data.get("reference_number", "")
        notes = request.data.get("notes", "")

        if not amount:
            return Response({"amount": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        bank_account = None
        if bank_account_id:
            try:
                bank_account = BankAccount.objects.get(pk=bank_account_id)
            except BankAccount.DoesNotExist:
                return Response({"bank_account": "Selected bank account not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = record_salary_payment(
                worker=salary_period.worker,
                amount=Decimal(str(amount)),
                salary_period=salary_period,
                payment_date=payment_date,
                payment_method=payment_method,
                bank_account=bank_account,
                reference_number=reference_number,
                notes=notes,
                user=request.user,
            )
            salary_period.refresh_from_db()
            return Response(
                {
                    "message": "Payment recorded successfully.",
                    "payment": WorkerSalaryPaymentSerializer(payment).data,
                    "salary_period": PowerLoomSalaryPeriodSerializer(salary_period).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class WorkerAdvanceViewSet(ModelViewSet):
    """
    CRUD and actions for Worker Advances.
    """
    queryset = WorkerAdvance.objects.select_related("worker", "bank_account", "created_by").all()
    serializer_class = WorkerAdvanceSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "payroll.process",
        "POST": "payroll.process",
        "PUT": "payroll.process",
        "PATCH": "payroll.process",
        "DELETE": "payroll.process",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkerAdvanceFilter
    search_fields = ["advance_number", "worker__name", "worker__worker_code", "notes"]
    ordering_fields = ["advance_date", "id", "amount", "remaining_advance"]
    ordering = ["-advance_date", "-id"]

    def create(self, request, *args, **kwargs):
        worker_id = request.data.get("worker")
        amount = request.data.get("amount")
        advance_date = request.data.get("advance_date") or str(timezone.localdate())
        payment_method = request.data.get("payment_method", "Cash")
        bank_account_id = request.data.get("bank_account")
        notes = request.data.get("notes", "")

        try:
            worker = Worker.objects.get(pk=worker_id)
        except Worker.DoesNotExist:
            return Response({"worker": "Worker not found."}, status=status.HTTP_400_BAD_REQUEST)

        bank_account = None
        if bank_account_id:
            try:
                bank_account = BankAccount.objects.get(pk=bank_account_id)
            except BankAccount.DoesNotExist:
                return Response({"bank_account": "Bank account not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            advance = record_worker_advance(
                worker=worker,
                amount=Decimal(str(amount)),
                advance_date=advance_date,
                payment_method=payment_method,
                bank_account=bank_account,
                notes=notes,
                user=request.user,
            )
            serializer = self.get_serializer(advance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class WorkerSalaryPaymentViewSet(ModelViewSet):
    """
    Salary payments (stand-alone or against salary period).
    """
    queryset = WorkerSalaryPayment.objects.select_related("worker", "salary_period", "bank_account", "created_by").all()
    serializer_class = WorkerSalaryPaymentSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "payroll.process",
        "POST": "payroll.process",
        "PUT": "payroll.process",
        "PATCH": "payroll.process",
        "DELETE": "payroll.process",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkerSalaryPaymentFilter
    search_fields = ["payment_number", "worker__name", "worker__worker_code", "reference_number", "notes"]
    ordering_fields = ["payment_date", "id", "amount"]
    ordering = ["-payment_date", "-id"]

    def create(self, request, *args, **kwargs):
        worker_id = request.data.get("worker")
        salary_period_id = request.data.get("salary_period")
        amount = request.data.get("amount")
        payment_date = request.data.get("payment_date") or str(timezone.localdate())
        payment_method = request.data.get("payment_method", "Cash")
        bank_account_id = request.data.get("bank_account")
        reference_number = request.data.get("reference_number", "")
        notes = request.data.get("notes", "")

        try:
            worker = Worker.objects.get(pk=worker_id)
        except Worker.DoesNotExist:
            return Response({"worker": "Worker not found."}, status=status.HTTP_400_BAD_REQUEST)

        salary_period = None
        if salary_period_id:
            try:
                salary_period = PowerLoomSalaryPeriod.objects.get(pk=salary_period_id)
            except PowerLoomSalaryPeriod.DoesNotExist:
                return Response({"salary_period": "Salary period not found."}, status=status.HTTP_400_BAD_REQUEST)

        bank_account = None
        if bank_account_id:
            try:
                bank_account = BankAccount.objects.get(pk=bank_account_id)
            except BankAccount.DoesNotExist:
                return Response({"bank_account": "Bank account not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = record_salary_payment(
                worker=worker,
                amount=Decimal(str(amount)),
                salary_period=salary_period,
                payment_date=payment_date,
                payment_method=payment_method,
                bank_account=bank_account,
                reference_number=reference_number,
                notes=notes,
                user=request.user,
            )
            serializer = self.get_serializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class WorkerSalaryLedgerViewSet(ReadOnlyModelViewSet):
    """
    Detailed, Chronological Power Loom Worker Salary Ledger.
    """
    queryset = WorkerSalaryLedger.objects.select_related(
        "worker",
        "salary_period",
        "attendance_record",
        "advance_record",
        "payment_record",
    ).all()
    serializer_class = WorkerSalaryLedgerSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    permission_map = {
        "GET": "payroll.process",
    }

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkerSalaryLedgerFilter
    search_fields = ["entry_number", "worker__name", "worker__worker_code", "reference_id", "description"]
    ordering_fields = ["date", "id", "running_balance", "daily_earned_amount", "payment_amount"]
    ordering = ["-date", "-id"]

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        qs = self.filter_queryset(self.get_queryset())
        total_earned = qs.aggregate(s=Sum("daily_earned_amount"))["s"] or Decimal("0.00")
        total_advances = qs.aggregate(s=Sum("advance_amount"))["s"] or Decimal("0.00")
        total_payments = qs.aggregate(s=Sum("payment_amount"))["s"] or Decimal("0.00")
        total_deductions = qs.aggregate(s=Sum("deduction_amount"))["s"] or Decimal("0.00")
        total_entries = qs.count()
        distinct_workers = qs.values("worker_id").distinct().count()

        net_outstanding = (total_earned - total_advances - total_payments - total_deductions).quantize(Decimal("0.01"))

        return Response({
            "total_earned": str(total_earned),
            "total_advances": str(total_advances),
            "total_payments": str(total_payments),
            "total_deductions": str(total_deductions),
            "net_outstanding": str(net_outstanding),
            "total_entries": total_entries,
            "distinct_workers": distinct_workers,
        })

