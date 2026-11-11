import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
from decimal import Decimal
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User
from factory.worker_salary.models import (
    Worker,
    WorkerAttendance,
    PowerLoomSalaryPeriod,
    WorkerAdvance,
    WorkerSalaryPayment,
    WorkerSalaryLedger,
)
from factory.worker_salary.services import (
    record_daily_attendance,
    calculate_salary_preview,
    finalize_salary_period,
    record_worker_advance,
    record_salary_payment,
    recalculate_worker_ledger,
)
from django.core.exceptions import ValidationError

print("--- Starting Power Loom Salary Verification ---")
admin_user = User.objects.filter(is_superuser=True).first()

# 1. Create a Power Loom Worker
worker = Worker.objects.create(
    name="Muhammad Aslam",
    cnic="35201-9876543-1",
    phone="03001234567",
    loom_type="Power Loom",
    daily_wage_rate=Decimal("1500.00"),
    preferred_payment_cycle="15 Days",
    designation="Master Power Loom Weaver",
    created_by=admin_user,
)
print(f"Created Worker: {worker.worker_code} - {worker.name}, Daily Wage: {worker.daily_wage_rate}")

# 2. Test Attendance
today = date.today()
# Attempt future date
try:
    record_daily_attendance(worker, today + timedelta(days=1), "Present")
    print("FAILED: Future attendance was not rejected!")
except ValidationError as e:
    print("PASS: Future attendance was correctly rejected:", e)

# Record 7 days attendance
# 5 Present (1.0), 1 Half Day (0.5), 1 Absent (0.0) -> Total working days = 5.5
days_data = [
    (today - timedelta(days=6), "Present"),
    (today - timedelta(days=5), "Present"),
    (today - timedelta(days=4), "Present"),
    (today - timedelta(days=3), "Present"),
    (today - timedelta(days=2), "Present"),
    (today - timedelta(days=1), "Half Day"),
    (today, "Absent"),
]
for d, st in days_data:
    record_daily_attendance(worker, d, st, user=admin_user)

worker.refresh_from_db()
print(f"After attendance: Worker current_balance: PKR {worker.current_balance}")
# Expected: 5 * 1500 = 7500, + 1 * 750 = 8250.
assert worker.current_balance == Decimal("8250.00"), f"Expected 8250, got {worker.current_balance}"
print("PASS: Attendance wage calculation exact (5.5 days @ 1500 = 8250.00)")

# 3. Test Advance
advance = record_worker_advance(
    worker=worker,
    amount=Decimal("2000.00"),
    advance_date=today - timedelta(days=2),
    payment_method="Cash",
    notes="Grocery advance",
    user=admin_user,
)
worker.refresh_from_db()
print(f"After Advance of 2000: Worker current_balance: PKR {worker.current_balance}")
assert worker.current_balance == Decimal("6250.00"), f"Expected 6250, got {worker.current_balance}"
print("PASS: Advance correctly debited running balance to 6250.00")

# 4. Test Salary Calculation Preview (Flexible cycle: Weekly 7 days)
start_d = today - timedelta(days=6)
end_d = today
preview = calculate_salary_preview(
    worker=worker,
    start_date=start_d,
    end_date=end_d,
    payment_cycle="Weekly",
    overtime_amount=Decimal("500.00"),
    other_earnings=Decimal("250.00"),
    other_deductions=Decimal("100.00"),
    advance_payments=Decimal("2000.00"),
)
print("Preview:", preview)
# Total Earned: 8250 base + 500 OT + 250 other = 9000.
# Net Payable: 9000 - 2000 adv - 100 ded = 6900.
assert Decimal(preview["total_earned_salary"]) == Decimal("9000.00"), f"Expected 9000 total earned, got {preview['total_earned_salary']}"
assert Decimal(preview["net_payable_balance"]) == Decimal("6900.00"), f"Expected 6900 net payable, got {preview['net_payable_balance']}"
print("PASS: Salary Preview exact!")

# 5. Finalize Salary Period
period = finalize_salary_period(
    worker=worker,
    start_date=start_d,
    end_date=end_d,
    payment_cycle="Weekly",
    overtime_amount=Decimal("500.00"),
    other_earnings=Decimal("250.00"),
    other_deductions=Decimal("100.00"),
    advance_payments=Decimal("2000.00"),
    notes="Week 1 Salary Period",
    user=admin_user,
)
print(f"Finalized Period: {period.calculation_number}, Status: {period.payment_status}, Net Payable: {period.net_payable_balance}")
assert period.payment_status == "Unpaid"

# 6. Test Multiple / Partial Payments
# Payment 1: 4000
pay1 = record_salary_payment(
    worker=worker,
    salary_period=period,
    amount=Decimal("4000.00"),
    payment_method="Cash",
    notes="Part 1 salary",
    user=admin_user,
)
period.refresh_from_db()
print(f"After Pay 1 (4000): Paid: {period.total_paid_amount}, Remaining: {period.net_payable_balance}, Status: {period.payment_status}")
assert period.payment_status == "Partial"
assert period.net_payable_balance == Decimal("2900.00")

# Payment 2: 2900 (Settles period completely)
pay2 = record_salary_payment(
    worker=worker,
    salary_period=period,
    amount=Decimal("2900.00"),
    payment_method="Cash",
    notes="Part 2 salary final settlement",
    user=admin_user,
)
period.refresh_from_db()
print(f"After Pay 2 (2900): Paid: {period.total_paid_amount}, Remaining: {period.net_payable_balance}, Status: {period.payment_status}")
assert period.payment_status == "Paid"
assert period.net_payable_balance == Decimal("0.00")
print("PASS: Partial and final payments verified!")

# 7. Test Ledger integrity
ledger_entries = WorkerSalaryLedger.objects.filter(worker=worker).order_by("date", "id")
print("\n--- Worker Salary Ledger ---")
for ent in ledger_entries:
    print(f"{ent.date} | {ent.entry_type:<15} | Earned: {ent.daily_earned_amount:7.2f} | Adv: {ent.advance_amount:7.2f} | Pay: {ent.payment_amount:7.2f} | Bal: {ent.running_balance:7.2f} | {ent.description}")

worker.refresh_from_db()
print(f"\nFinal Worker Balance: PKR {worker.current_balance}")
assert worker.current_balance == Decimal("0.00"), f"Expected 0.00, got {worker.current_balance}"
print("--- ALL VERIFICATIONS PASSED SUCCESSFULLY! ---")
