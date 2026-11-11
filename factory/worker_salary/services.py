"""
Services for Power Loom Worker Salary & Attendance module.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from factory.bank_account.models import BankAccount, BankTransaction
from .models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)


from datetime import date as dt_date

def _is_future_date(target_date) -> bool:
    if isinstance(target_date, str):
        target_date = dt_date.fromisoformat(target_date)
    today_local = timezone.localdate()
    today_sys = dt_date.today()
    max_today = max(today_local, today_sys)
    return target_date > max_today


@transaction.atomic
def record_daily_attendance(
    worker: Worker,
    date,
    status: str,
    daily_wage_rate=None,
    per_meter_rate=None,
    meters_produced=None,
    notes: str = "",
    user=None,
) -> WorkerAttendance:
    """
    Records or updates daily attendance / daily fabric production for a worker.
    """
    if _is_future_date(date):
        raise ValidationError("Future dates cannot be recorded as working days.")

    existing_att = WorkerAttendance.objects.filter(worker=worker, date=date).first()
    if existing_att and existing_att.is_salary_processed:
        raise ValidationError(
            f"Attendance for {date} has already been processed in salary calculation "
            f"{existing_att.salary_period.calculation_number if existing_att.salary_period else ''}. "
            "It cannot be modified."
        )

    rate = Decimal(str(daily_wage_rate)) if daily_wage_rate is not None else worker.daily_wage_rate
    m_rate = Decimal(str(per_meter_rate)) if per_meter_rate is not None else worker.per_meter_rate
    meters = Decimal(str(meters_produced or "0.00"))

    if existing_att:
        existing_att.status = status
        existing_att.daily_wage_rate = rate
        existing_att.per_meter_rate = m_rate
        existing_att.meters_produced = meters
        existing_att.notes = notes
        existing_att.save()
        attendance = existing_att
    else:
        attendance = WorkerAttendance.objects.create(
            worker=worker,
            date=date,
            status=status,
            daily_wage_rate=rate,
            per_meter_rate=m_rate,
            meters_produced=meters,
            notes=notes,
            created_by=user,
        )

    # Sync with WorkerSalaryLedger
    ledger_entry = WorkerSalaryLedger.objects.filter(
        worker=worker,
        attendance_record=attendance,
    ).first()

    is_manual = worker.loom_type == Worker.LoomTypeChoices.MANUAL_LOOM
    multiplier = attendance.wage_multiplier
    earned = attendance.earned_amount

    desc = (
        f"Manual Loom Production: {meters}m @ Rs. {m_rate:,.2f}/m ({status})"
        if is_manual
        else f"Daily attendance: {status} ({multiplier * 100}% of Rs. {rate:,.2f})"
    )
    entry_type = (
        WorkerSalaryLedger.EntryTypeChoices.FABRIC_PRODUCTION
        if is_manual
        else WorkerSalaryLedger.EntryTypeChoices.DAILY_WAGE
    )

    if not ledger_entry:
        ledger_entry = WorkerSalaryLedger(
            worker=worker,
            worker_name=worker.name,
            date=date,
            entry_type=entry_type,
            daily_wage_rate=rate,
            per_meter_rate=m_rate,
            meters_produced=meters,
            attendance_status=status,
            daily_earned_amount=earned,
            reference_id=f"ATT-{attendance.id}",
            description=desc,
            attendance_record=attendance,
            created_by=user,
        )
    else:
        ledger_entry.entry_type = entry_type
        ledger_entry.daily_wage_rate = rate
        ledger_entry.per_meter_rate = m_rate
        ledger_entry.meters_produced = meters
        ledger_entry.attendance_status = status
        ledger_entry.daily_earned_amount = earned
        ledger_entry.description = desc

    ledger_entry.save()

    recalculate_worker_ledger(worker)
    return attendance


def calculate_salary_preview(
    worker: Worker,
    start_date=None,
    end_date=None,
    payment_cycle: str = "15 Days",
    overtime_amount=Decimal("0.00"),
    other_earnings=Decimal("0.00"),
    other_deductions=Decimal("0.00"),
    advance_payments=None,
    total_working_days=None,
    total_meters_produced=None,
):
    """
    Computes real-time salary calculation preview without saving to DB.
    Supports both Power Loom (Daily Wage * Working Days) and Manual Loom (Per Meter Rate * Meters Produced).
    """
    today = timezone.localdate()
    start_date = start_date or today
    end_date = end_date or today

    overtime_amount = Decimal(str(overtime_amount or "0.00"))
    other_earnings = Decimal(str(other_earnings or "0.00"))
    other_deductions = Decimal(str(other_deductions or "0.00"))

    attendances = WorkerAttendance.objects.filter(
        worker=worker,
        date__gte=start_date,
        date__lte=end_date,
        is_salary_processed=False,
    ).order_by("date")

    present_count = Decimal("0.00")
    half_day_count = Decimal("0.00")
    absent_count = Decimal("0.00")
    leave_count = Decimal("0.00")
    logged_meters = Decimal("0.00")

    for att in attendances:
        if att.status == WorkerAttendance.AttendanceStatusChoices.PRESENT:
            present_count += Decimal("1.00")
        elif att.status == WorkerAttendance.AttendanceStatusChoices.HALF_DAY:
            half_day_count += Decimal("1.00")
        elif att.status == WorkerAttendance.AttendanceStatusChoices.ABSENT:
            absent_count += Decimal("1.00")
        elif att.status == WorkerAttendance.AttendanceStatusChoices.LEAVE:
            leave_count += Decimal("1.00")
        logged_meters += att.meters_produced

    logged_working_days = present_count + (half_day_count * Decimal("0.50"))

    if total_working_days is not None and str(total_working_days) != "":
        days_total = Decimal(str(total_working_days))
        present_count = days_total
    else:
        days_total = logged_working_days

    is_manual = worker.loom_type == Worker.LoomTypeChoices.MANUAL_LOOM
    if total_meters_produced is not None and str(total_meters_produced) != "":
        meters_total = Decimal(str(total_meters_produced))
    else:
        meters_total = logged_meters

    if is_manual:
        base_earned = (worker.per_meter_rate * meters_total).quantize(Decimal("0.01"))
    else:
        base_earned = (worker.daily_wage_rate * days_total).quantize(Decimal("0.01"))

    total_earned_salary = (base_earned + overtime_amount + other_earnings).quantize(Decimal("0.01"))

    unsettled_advances = WorkerAdvance.objects.filter(
        worker=worker,
        status__in=[WorkerAdvance.StatusChoices.ACTIVE, WorkerAdvance.StatusChoices.PARTIALLY_DEDUCTED],
        advance_date__lte=end_date,
    )
    total_unsettled_advances = sum(
        (adv.remaining_advance for adv in unsettled_advances), Decimal("0.00")
    )

    if advance_payments is None:
        advances_to_deduct = min(total_unsettled_advances, total_earned_salary)
    else:
        advances_to_deduct = Decimal(str(advance_payments))

    net_payable = (
        total_earned_salary - advances_to_deduct - other_deductions
    ).quantize(Decimal("0.01"))

    return {
        "worker_id": worker.id,
        "worker_code": worker.worker_code,
        "worker_name": worker.name,
        "loom_type": worker.loom_type,
        "daily_wage_rate": str(worker.daily_wage_rate),
        "per_meter_rate": str(worker.per_meter_rate),
        "total_meters_produced": float(meters_total),
        "logged_meters": float(logged_meters),
        "logged_working_days": float(logged_working_days),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "payment_cycle": payment_cycle,
        "present_days": float(present_count),
        "half_days": float(half_day_count),
        "absent_days": float(absent_count),
        "leave_days": float(leave_count),
        "total_working_days": float(days_total),
        "base_earned_salary": str(base_earned),
        "overtime_amount": str(overtime_amount),
        "other_earnings": str(other_earnings),
        "total_earned_salary": str(total_earned_salary),
        "available_advances": str(total_unsettled_advances),
        "advance_payments": str(advances_to_deduct),
        "other_deductions": str(other_deductions),
        "net_payable_balance": str(net_payable),
        "attendance_count": attendances.count(),
    }


@transaction.atomic
def finalize_salary_period(
    worker: Worker,
    start_date=None,
    end_date=None,
    payment_cycle: str = "15 Days",
    overtime_amount=Decimal("0.00"),
    other_earnings=Decimal("0.00"),
    other_deductions=Decimal("0.00"),
    advance_payments=None,
    total_working_days=None,
    total_meters_produced=None,
    notes: str = "",
    user=None,
) -> PowerLoomSalaryPeriod:
    """
    Creates and finalizes a salary period calculation for Power Loom or Manual Loom.
    """
    today = timezone.localdate()
    start_date = start_date or today
    end_date = end_date or today

    preview = calculate_salary_preview(
        worker=worker,
        start_date=start_date,
        end_date=end_date,
        payment_cycle=payment_cycle,
        overtime_amount=overtime_amount,
        other_earnings=other_earnings,
        other_deductions=other_deductions,
        advance_payments=advance_payments,
        total_working_days=total_working_days,
        total_meters_produced=total_meters_produced,
    )

    salary_period = PowerLoomSalaryPeriod.objects.create(
        worker=worker,
        worker_name=worker.name,
        loom_type=worker.loom_type,
        daily_wage_rate=worker.daily_wage_rate,
        per_meter_rate=worker.per_meter_rate,
        total_meters_produced=Decimal(str(preview["total_meters_produced"])),
        start_date=start_date,
        end_date=end_date,
        payment_cycle=payment_cycle,
        total_working_days=Decimal(str(preview["total_working_days"])),
        present_days=Decimal(str(preview["present_days"])),
        half_days=Decimal(str(preview["half_days"])),
        absent_days=Decimal(str(preview["absent_days"])),
        leave_days=Decimal(str(preview["leave_days"])),
        base_earned_salary=Decimal(str(preview["base_earned_salary"])),
        overtime_amount=Decimal(str(preview["overtime_amount"])),
        other_earnings=Decimal(str(preview["other_earnings"])),
        total_earned_salary=Decimal(str(preview["total_earned_salary"])),
        advance_payments=Decimal(str(preview["advance_payments"])),
        other_deductions=Decimal(str(preview["other_deductions"])),
        total_paid_amount=Decimal("0.00"),
        net_payable_balance=Decimal(str(preview["net_payable_balance"])),
        payment_status=PowerLoomSalaryPeriod.PaymentStatusChoices.UNPAID,
        notes=notes,
        created_by=user,
    )

    # Record earned salary in WorkerSalaryLedger for Manual Loom or Power Loom
    if worker.loom_type == Worker.LoomTypeChoices.MANUAL_LOOM:
        unlogged_meters = Decimal(str(preview["total_meters_produced"])) - Decimal(str(preview["logged_meters"]))
        if unlogged_meters > Decimal("0.00"):
            unlogged_earned = (worker.per_meter_rate * unlogged_meters).quantize(Decimal("0.01"))
            WorkerSalaryLedger.objects.create(
                worker=worker,
                worker_name=worker.name,
                date=end_date,
                entry_type=WorkerSalaryLedger.EntryTypeChoices.FABRIC_PRODUCTION,
                per_meter_rate=worker.per_meter_rate,
                meters_produced=unlogged_meters,
                daily_earned_amount=unlogged_earned,
                payment_cycle=payment_cycle,
                reference_id=salary_period.calculation_number,
                description=f"Fabric Production: {unlogged_meters}m @ Rs. {worker.per_meter_rate:,.2f}/m ({salary_period.calculation_number})",
                salary_period=salary_period,
                created_by=user,
            )
    else:
        unlogged_days = Decimal(str(preview["total_working_days"])) - Decimal(str(preview["logged_working_days"]))
        if unlogged_days > Decimal("0.00"):
            unlogged_earned = (worker.daily_wage_rate * unlogged_days).quantize(Decimal("0.01"))
            WorkerSalaryLedger.objects.create(
                worker=worker,
                worker_name=worker.name,
                date=end_date,
                entry_type=WorkerSalaryLedger.EntryTypeChoices.DAILY_WAGE,
                daily_wage_rate=worker.daily_wage_rate,
                attendance_status=f"{unlogged_days} Working Days",
                daily_earned_amount=unlogged_earned,
                payment_cycle=payment_cycle,
                reference_id=salary_period.calculation_number,
                description=f"Power Loom Salary: {unlogged_days} days @ Rs. {worker.daily_wage_rate:,.2f}/day ({salary_period.calculation_number})",
                salary_period=salary_period,
                created_by=user,
            )

    # Lock attendance in this range
    attendances = WorkerAttendance.objects.filter(
        worker=worker,
        date__gte=start_date,
        date__lte=end_date,
    )
    attendances.update(
        is_salary_processed=True,
        salary_period=salary_period,
    )

    # Apply advance deductions against active advances
    adv_remaining_to_deduct = salary_period.advance_payments
    if adv_remaining_to_deduct > Decimal("0.00"):
        active_advances = WorkerAdvance.objects.filter(
            worker=worker,
            status__in=[WorkerAdvance.StatusChoices.ACTIVE, WorkerAdvance.StatusChoices.PARTIALLY_DEDUCTED],
            advance_date__lte=end_date,
        ).order_by("advance_date", "id")

        for adv in active_advances:
            if adv_remaining_to_deduct <= Decimal("0.00"):
                break
            can_deduct = min(adv.remaining_advance, adv_remaining_to_deduct)
            adv.amount_deducted += can_deduct
            adv.salary_period = salary_period
            adv.save()
            adv_remaining_to_deduct -= can_deduct

    # Record overtime / other earnings in ledger if any
    if salary_period.overtime_amount > Decimal("0.00") or salary_period.other_earnings > Decimal("0.00"):
        extra = salary_period.overtime_amount + salary_period.other_earnings
        WorkerSalaryLedger.objects.create(
            worker=worker,
            worker_name=worker.name,
            date=end_date,
            entry_type=WorkerSalaryLedger.EntryTypeChoices.OVERTIME_OTHER,
            daily_wage_rate=salary_period.daily_wage_rate,
            daily_earned_amount=extra,
            payment_cycle=payment_cycle,
            reference_id=salary_period.calculation_number,
            description=f"Overtime (Rs. {salary_period.overtime_amount:,.2f}) + Other Earnings (Rs. {salary_period.other_earnings:,.2f})",
            salary_period=salary_period,
            created_by=user,
        )

    # Record other deduction in ledger if any
    if salary_period.other_deductions > Decimal("0.00"):
        WorkerSalaryLedger.objects.create(
            worker=worker,
            worker_name=worker.name,
            date=end_date,
            entry_type=WorkerSalaryLedger.EntryTypeChoices.DEDUCTION,
            daily_wage_rate=salary_period.daily_wage_rate,
            deduction_amount=salary_period.other_deductions,
            payment_cycle=payment_cycle,
            reference_id=salary_period.calculation_number,
            description=f"Salary deduction for period {salary_period.calculation_number}",
            salary_period=salary_period,
            created_by=user,
        )

    recalculate_worker_ledger(worker)
    return salary_period


@transaction.atomic
def record_worker_advance(
    worker: Worker,
    amount: Decimal,
    advance_date=None,
    payment_method: str = "Cash",
    bank_account: BankAccount = None,
    notes: str = "",
    user=None,
) -> WorkerAdvance:
    """
    Issues an advance payment to worker.
    - Creates WorkerAdvance record.
    - Posts a debit to the selected bank account if bank payment method.
    - Posts Advance debit entry to WorkerSalaryLedger.
    - Updates Worker running balances.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal("0.00"):
        raise ValidationError("Advance amount must be greater than zero.")

    advance_date = advance_date or timezone.localdate()

    bank_txn = None
    if bank_account and payment_method in ["Online Transfer", "Cheque"]:
        bank_txn = BankTransaction.objects.create(
            bank_account=bank_account,
            transaction_type=BankTransaction.TransactionType.DEBIT,
            amount=amount,
            date=advance_date,
            payment_method=payment_method,
            party_name=worker.name,
            description=f"Worker advance issued to {worker.name} ({worker.worker_code})",
            created_by=user,
        )

    advance = WorkerAdvance.objects.create(
        worker=worker,
        advance_date=advance_date,
        amount=amount,
        amount_deducted=Decimal("0.00"),
        remaining_advance=amount,
        payment_method=payment_method,
        bank_account=bank_account,
        bank_transaction=bank_txn,
        notes=notes,
        created_by=user,
    )

    # Create Ledger entry
    WorkerSalaryLedger.objects.create(
        worker=worker,
        worker_name=worker.name,
        date=advance_date,
        entry_type=WorkerSalaryLedger.EntryTypeChoices.ADVANCE,
        daily_wage_rate=worker.daily_wage_rate,
        advance_amount=amount,
        reference_id=advance.advance_number,
        description=f"Advance paid via {payment_method}{f' ({bank_account.bank_name})' if bank_account else ''}: {notes}",
        advance_record=advance,
        created_by=user,
    )

    recalculate_worker_ledger(worker)
    return advance


@transaction.atomic
def record_salary_payment(
    worker: Worker,
    amount: Decimal,
    salary_period: PowerLoomSalaryPeriod = None,
    payment_date=None,
    payment_method: str = "Cash",
    bank_account: BankAccount = None,
    reference_number: str = "",
    notes: str = "",
    user=None,
) -> WorkerSalaryPayment:
    """
    Processes a partial or full salary payment to worker.
    - Validates amount > 0.
    - Updates PowerLoomSalaryPeriod total_paid_amount, net_payable_balance, and payment_status.
    - Deducts from BankAccount if bank transfer / cheque.
    - Posts Payment entry to WorkerSalaryLedger.
    - Updates Worker total_paid_amount and current_balance.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal("0.00"):
        raise ValidationError("Payment amount must be greater than zero.")

    payment_date = payment_date or timezone.localdate()

    bank_txn = None
    if bank_account and payment_method in ["Online Transfer", "Cheque"]:
        bank_txn = BankTransaction.objects.create(
            bank_account=bank_account,
            transaction_type=BankTransaction.TransactionType.DEBIT,
            amount=amount,
            date=payment_date,
            payment_method=payment_method,
            party_name=worker.name,
            reference_number=reference_number,
            description=f"Salary payment to {worker.name} ({worker.worker_code})",
            created_by=user,
        )

    payment = WorkerSalaryPayment.objects.create(
        worker=worker,
        salary_period=salary_period,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        bank_account=bank_account,
        bank_transaction=bank_txn,
        reference_number=reference_number,
        notes=notes,
        created_by=user,
    )

    # Update salary period if linked
    if salary_period:
        salary_period.total_paid_amount = (
            salary_period.total_paid_amount + amount
        ).quantize(Decimal("0.01"))
        salary_period.update_financials()
        salary_period.save()

    # Create Ledger Entry
    cycle = salary_period.payment_cycle if salary_period else worker.preferred_payment_cycle
    status_label = salary_period.payment_status if salary_period else "Paid"
    period_ref = f" against {salary_period.calculation_number}" if salary_period else ""

    WorkerSalaryLedger.objects.create(
        worker=worker,
        worker_name=worker.name,
        date=payment_date,
        entry_type=WorkerSalaryLedger.EntryTypeChoices.PAYMENT,
        daily_wage_rate=worker.daily_wage_rate,
        payment_amount=amount,
        payment_cycle=cycle,
        payment_status=status_label,
        reference_id=payment.payment_number,
        description=f"Salary payment{period_ref} via {payment_method}. {reference_number} {notes}".strip(),
        salary_period=salary_period,
        payment_record=payment,
        created_by=user,
    )

    recalculate_worker_ledger(worker)
    return payment


@transaction.atomic
def recalculate_worker_ledger(worker: Worker):
    """
    Recalculates the chronological running balance for a worker across all ledger entries.
    Ensures 100% mathematical precision and synchronization.
    Formula:
        Balance = sum(Daily Earned) - sum(Advance) - sum(Deduction) - sum(Payment)
    """
    entries = WorkerSalaryLedger.objects.filter(worker=worker).order_by("date", "id")

    balance = Decimal("0.00")
    total_earned = Decimal("0.00")
    total_advance = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_deduction = Decimal("0.00")

    for entry in entries:
        total_earned += entry.daily_earned_amount
        total_advance += entry.advance_amount
        total_paid += entry.payment_amount
        total_deduction += entry.deduction_amount

        balance = (
            balance + entry.daily_earned_amount - entry.advance_amount - entry.payment_amount - entry.deduction_amount
        ).quantize(Decimal("0.01"))

        if entry.running_balance != balance:
            entry.running_balance = balance
            entry.save(update_fields=["running_balance"])

    # Update worker denormalized summary
    worker.total_earned_amount = total_earned
    worker.total_advance_amount = total_advance
    worker.total_paid_amount = total_paid
    worker.current_balance = balance
    worker.save(update_fields=[
        "total_earned_amount",
        "total_advance_amount",
        "total_paid_amount",
        "current_balance",
    ])
