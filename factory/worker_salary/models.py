"""
Models for Power Loom Worker Salary – Daily Wage & Flexible Payment System.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from factory.bank_account.models import BankAccount, BankTransaction


class Worker(models.Model):
    """
    Worker profile, daily wage rate, and running financial balance.
    """
    class LoomTypeChoices(models.TextChoices):
        POWER_LOOM = "Power Loom", "Power Loom"
        AUTO_LOOM = "Auto Loom", "Auto Loom"
        SULZER_LOOM = "Sulzer Loom", "Sulzer Loom"
        AIRJET_LOOM = "Airjet Loom", "Airjet Loom"
        OTHER = "Other", "Other"

    class PaymentCycleChoices(models.TextChoices):
        WEEKLY = "Weekly", "Weekly (Every 7 Days)"
        BI_WEEKLY = "15 Days", "Every 15 Days"
        MONTHLY = "Monthly", "Monthly (Every Month)"
        CUSTOM = "Custom", "Custom Date Range"

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    worker_code = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=255)
    cnic = models.CharField(max_length=50, blank=True, default="", help_text="e.g. 35201-1234567-1")
    phone = models.CharField(max_length=50, blank=True, default="")
    photo = models.ImageField(upload_to="workers/photos/", null=True, blank=True)
    loom_type = models.CharField(
        max_length=50,
        choices=LoomTypeChoices.choices,
        default=LoomTypeChoices.POWER_LOOM,
    )
    daily_wage_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Standard daily wage rate for this worker",
    )
    preferred_payment_cycle = models.CharField(
        max_length=30,
        choices=PaymentCycleChoices.choices,
        default=PaymentCycleChoices.BI_WEEKLY,
    )
    designation = models.CharField(max_length=100, default="Power Loom Weaver")
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )
    joining_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, default="")
    emergency_contact = models.CharField(max_length=100, blank=True, default="")

    # Running financial summary for quick dashboards
    total_earned_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_advance_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net payable balance owed by factory to the worker",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.worker_code} - {self.name} ({self.loom_type})"

    def save(self, *args, **kwargs):
        if not self.worker_code:
            last = Worker.objects.order_by("-id").first()
            new_id = (last.id + 1) if last else 1
            self.worker_code = f"WRK-{new_id:04d}"
        super().save(*args, **kwargs)


class WorkerAttendance(models.Model):
    """
    Daily attendance record for a worker with wage calculation.
    """
    class AttendanceStatusChoices(models.TextChoices):
        PRESENT = "Present", "Present (Full Day)"
        HALF_DAY = "Half Day", "Half Day (50% Wage)"
        ABSENT = "Absent", "Absent (0% Wage)"
        LEAVE = "Leave", "Leave"

    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    date = models.DateField(help_text="Attendance date (cannot be in the future)")
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatusChoices.choices,
        default=AttendanceStatusChoices.PRESENT,
    )
    daily_wage_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Daily wage rate effective on this date",
    )
    wage_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Present=1.0, Half Day=0.5, Absent=0.0, Leave=0.0",
    )
    earned_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="daily_wage_rate * wage_multiplier",
    )
    is_salary_processed = models.BooleanField(
        default=False,
        help_text="Whether this day's attendance has been locked/settled in a finalized salary calculation",
    )
    salary_period = models.ForeignKey(
        "PowerLoomSalaryPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendances",
    )
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_attendances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["worker", "date"],
                name="unique_worker_attendance_per_date",
            )
        ]

    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError({"date": "Future dates cannot be recorded as working days."})

    def save(self, *args, **kwargs):
        self.clean()
        if not self.daily_wage_rate:
            self.daily_wage_rate = self.worker.daily_wage_rate

        # Multiplier rules: Present=1.0, Half Day=0.5, Absent=0.0, Leave=0.0
        if self.status == self.AttendanceStatusChoices.PRESENT:
            self.wage_multiplier = Decimal("1.00")
        elif self.status == self.AttendanceStatusChoices.HALF_DAY:
            self.wage_multiplier = Decimal("0.50")
        elif self.status == self.AttendanceStatusChoices.ABSENT:
            self.wage_multiplier = Decimal("0.00")
        elif self.status == self.AttendanceStatusChoices.LEAVE:
            self.wage_multiplier = Decimal("0.00")
        else:
            self.wage_multiplier = Decimal("1.00")

        self.earned_amount = (self.daily_wage_rate * self.wage_multiplier).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker.name} - {self.date} ({self.status}: PKR {self.earned_amount})"


class PowerLoomSalaryPeriod(models.Model):
    """
    Formal salary calculation cycle for a Power Loom worker.
    Supports Weekly, 15 Days, Monthly, or Custom Date Range.
    """
    class PaymentCycleChoices(models.TextChoices):
        WEEKLY = "Weekly", "Weekly (Every 7 Days)"
        BI_WEEKLY = "15 Days", "Every 15 Days"
        MONTHLY = "Monthly", "Monthly (Every Month)"
        CUSTOM = "Custom", "Custom Date Range"

    class PaymentStatusChoices(models.TextChoices):
        UNPAID = "Unpaid", "Unpaid"
        PARTIAL = "Partial", "Partial"
        PAID = "Paid", "Paid"

    calculation_number = models.CharField(max_length=50, unique=True, editable=False)
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="salary_periods",
    )
    worker_name = models.CharField(max_length=255)
    daily_wage_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Historical daily wage rate snapshot for this calculation",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    payment_cycle = models.CharField(
        max_length=30,
        choices=PaymentCycleChoices.choices,
        default=PaymentCycleChoices.BI_WEEKLY,
    )

    # Attendance breakdown
    total_working_days = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated from attendance (Present*1 + HalfDay*0.5)",
    )
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    half_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    absent_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    # Earnings & Calculation
    base_earned_salary = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Daily Wage Rate * Total Working Days",
    )
    overtime_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    other_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_earned_salary = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="(Daily Wage Rate * Total Working Days) + Overtime + Other Earnings",
    )

    # Deductions & Settlements
    advance_payments = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Advances deducted against this salary period",
    )
    other_deductions = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_paid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Sum of all payments made towards this salary period",
    )
    net_payable_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total Earned Salary - Advance Payments - Other Deductions - Total Paid Amount",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID,
    )
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salary_periods",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.calculation_number} - {self.worker_name} ({self.start_date} to {self.end_date})"

    def update_financials(self):
        """
        Recalculates totals and updates payment_status.
        """
        self.base_earned_salary = (self.daily_wage_rate * self.total_working_days).quantize(Decimal("0.01"))
        self.total_earned_salary = (
            self.base_earned_salary + self.overtime_amount + self.other_earnings
        ).quantize(Decimal("0.01"))

        # Payable net of deductions
        net_due = self.total_earned_salary - self.advance_payments - self.other_deductions
        self.net_payable_balance = (net_due - self.total_paid_amount).quantize(Decimal("0.01"))

        if self.total_paid_amount <= 0:
            self.payment_status = self.PaymentStatusChoices.UNPAID
        elif self.net_payable_balance <= Decimal("0.00"):
            self.payment_status = self.PaymentStatusChoices.PAID
        else:
            self.payment_status = self.PaymentStatusChoices.PARTIAL

    def save(self, *args, **kwargs):
        if not self.calculation_number:
            last = PowerLoomSalaryPeriod.objects.order_by("-id").first()
            new_id = (last.id + 1) if last else 1
            self.calculation_number = f"SAL-{new_id:04d}"
        if not self.worker_name and self.worker:
            self.worker_name = self.worker.name
        if not self.daily_wage_rate and self.worker:
            self.daily_wage_rate = self.worker.daily_wage_rate

        self.update_financials()
        super().save(*args, **kwargs)


class WorkerAdvance(models.Model):
    """
    Advance payments made to a worker (separate from salary payments).
    """
    class PaymentMethodChoices(models.TextChoices):
        CASH = "Cash", "Cash"
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer"
        CHEQUE = "Cheque", "Cheque"
        OTHER = "Other", "Other"

    class StatusChoices(models.TextChoices):
        ACTIVE = "Active", "Active / Outstanding"
        PARTIALLY_DEDUCTED = "Partially Deducted", "Partially Deducted"
        FULLY_DEDUCTED = "Fully Deducted", "Fully Deducted"

    advance_number = models.CharField(max_length=50, unique=True, editable=False)
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="advances",
    )
    advance_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    remaining_advance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.CASH,
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worker_advances",
    )
    bank_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worker_advance_origins",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )
    salary_period = models.ForeignKey(
        PowerLoomSalaryPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settled_advances",
    )
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_worker_advances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-advance_date", "-id"]

    def __str__(self):
        return f"{self.advance_number} - {self.worker.name} (PKR {self.amount})"

    def save(self, *args, **kwargs):
        if not self.advance_number:
            last = WorkerAdvance.objects.order_by("-id").first()
            new_id = (last.id + 1) if last else 1
            self.advance_number = f"ADV-{new_id:04d}"

        self.remaining_advance = (self.amount - self.amount_deducted).quantize(Decimal("0.01"))
        if self.amount_deducted >= self.amount:
            self.status = self.StatusChoices.FULLY_DEDUCTED
        elif self.amount_deducted > Decimal("0.00"):
            self.status = self.StatusChoices.PARTIALLY_DEDUCTED
        else:
            self.status = self.StatusChoices.ACTIVE

        super().save(*args, **kwargs)


class WorkerSalaryPayment(models.Model):
    """
    Multiple / partial payment against a salary period or general worker account.
    """
    class PaymentMethodChoices(models.TextChoices):
        CASH = "Cash", "Cash"
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer"
        CHEQUE = "Cheque", "Cheque"
        OTHER = "Other", "Other"

    payment_number = models.CharField(max_length=50, unique=True, editable=False)
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="salary_payments",
    )
    salary_period = models.ForeignKey(
        PowerLoomSalaryPeriod,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )
    payment_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.CASH,
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worker_salary_payments",
    )
    bank_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worker_salary_payment_origins",
    )
    reference_number = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salary_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"{self.payment_number} - {self.worker.name}: PKR {self.amount}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            last = WorkerSalaryPayment.objects.order_by("-id").first()
            new_id = (last.id + 1) if last else 1
            self.payment_number = f"WSP-{new_id:04d}"
        super().save(*args, **kwargs)


class WorkerSalaryLedger(models.Model):
    """
    Detailed, chronological worker salary ledger showing:
    - Date
    - Worker Name
    - Daily Wage
    - Attendance
    - Daily Earned Amount
    - Advance
    - Payment
    - Remaining Balance
    """
    class EntryTypeChoices(models.TextChoices):
        DAILY_WAGE = "Daily Wage", "Daily Wage Earned"
        OVERTIME_OTHER = "Overtime/Other", "Overtime / Other Earnings"
        ADVANCE = "Advance", "Advance Given"
        PAYMENT = "Payment", "Salary Payment"
        DEDUCTION = "Deduction", "Other Deduction"

    entry_number = models.CharField(max_length=50, unique=True, editable=False)
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    worker_name = models.CharField(max_length=255, blank=True, default="")
    date = models.DateField()
    entry_type = models.CharField(
        max_length=30,
        choices=EntryTypeChoices.choices,
    )
    daily_wage_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    attendance_status = models.CharField(max_length=30, blank=True, default="")
    daily_earned_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Credit: money earned by worker (+ balance)",
    )
    advance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Debit: cash given in advance (- balance)",
    )
    payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Debit: salary payout to worker (- balance)",
    )
    deduction_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Debit: penalty or deduction (- balance)",
    )
    running_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative net payable balance owed to worker after this transaction",
    )
    payment_cycle = models.CharField(max_length=30, blank=True, default="15 Days")
    payment_status = models.CharField(max_length=20, blank=True, default="")
    reference_id = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")

    salary_period = models.ForeignKey(
        PowerLoomSalaryPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    attendance_record = models.ForeignKey(
        WorkerAttendance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    advance_record = models.ForeignKey(
        WorkerAdvance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    payment_record = models.ForeignKey(
        WorkerSalaryPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_worker_ledger_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.entry_number} - {self.worker_name} ({self.date}): Bal {self.running_balance}"

    def save(self, *args, **kwargs):
        if not self.entry_number:
            last = WorkerSalaryLedger.objects.order_by("-id").first()
            new_id = (last.id + 1) if last else 1
            self.entry_number = f"WSL-{new_id:04d}"
        if not self.worker_name and self.worker:
            self.worker_name = self.worker.name
        super().save(*args, **kwargs)
