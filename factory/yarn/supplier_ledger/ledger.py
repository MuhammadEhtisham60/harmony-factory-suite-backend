"""
Yarn Supplier Ledger computation engine.

The ledger is a read-only, computed view built from:
  1. INTAKE (Yarn received from a supplier) -> YarnIntake
  2. PAYMENT (Payments made to a supplier) -> YarnSupplierPayment

Running balances are accumulated per supplier in exact Decimal
with NO float conversion, NO silent rounding, and large context precision.
"""

from datetime import date as date_type
from decimal import Decimal, localcontext

from django.db.models import Sum, Count, Q
from django.utils.dateparse import parse_date

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_intake.models import YarnIntake
from factory.yarn.yarn_stock.models import LB_PER_KG
from .models import YarnSupplierPayment

ZERO = Decimal("0")
LEDGER_DECIMAL_PRECISION = 60

ENTRY_INTAKE = "intake"
ENTRY_PAYMENT = "payment"
ENTRY_TYPES = (ENTRY_INTAKE, ENTRY_PAYMENT)

CSV_COLUMNS = [
    ("Date", "date"),
    ("Type", "entry_type"),
    ("Supplier Code", "supplier_code"),
    ("Supplier Name", "supplier_name"),
    ("Reference", "reference"),
    ("Yarn Quality", "yarn_quality"),
    ("Production Type", "production_type"),
    ("Bags In", "bags_in"),
    ("Cones In", "cones_in"),
    ("Weight In (kg)", "weight_kg_in"),
    ("Weight In (lb)", "weight_lb_in"),
    ("Rate / lb", "rate_per_lb"),
    ("Purchase Amount", "purchase_amount"),
    ("Payment Method", "payment_method"),
    ("Payment Amount", "payment_amount"),
    ("Amount Paid", "amount_paid"),
    ("Amount Due", "amount_due"),
    ("Payment Status", "payment_status"),
    ("Remaining Bags", "remaining_bags"),
    ("Balance Bags", "balance_bags"),
    ("Balance Weight (kg)", "balance_weight_kg"),
    ("Balance Weight (lb)", "balance_weight_lb"),
    ("Balance Payables", "balance_payables"),
    ("Remarks", "remarks"),
]

MAIN_CSV_COLUMNS = [
    ("Supplier Code", "supplier_code"),
    ("Supplier Name", "supplier_name"),
    ("Company Name", "company_name"),
    ("Contact Person", "contact_person"),
    ("Phone", "phone"),
    ("Email", "email"),
    ("Status", "status"),
    ("Bags Received", "total_bags_received"),
    ("Remaining Bags", "total_remaining_bags"),
    ("Weight Received (kg)", "total_weight_kg_received"),
    ("Remaining Weight (kg)", "total_remaining_weight_kg"),
    ("Weight Received (lb)", "total_weight_lb_received"),
    ("Total Purchases", "total_purchases"),
    ("Total Paid", "total_paid"),
    ("Total Payables", "total_payables"),
    ("Intakes Count", "intakes_count"),
    ("Payments Count", "payments_count"),
    ("Transactions Count", "transactions_count"),
]


def _dec(value):
    """Return value as an exact Decimal (None -> ZERO). Never converts to float."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def exact_str(value):
    """Full-precision plain-notation string for a Decimal (no scientific exponent).
    Normalizes unnecessary trailing zeros if present after a decimal point."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        s = format(value, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
            if not s:
                s = "0"
        return s
    return str(value)


def csv_value(val):
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return exact_str(val)
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (date_type,)):
        return val.isoformat()
    return str(val).strip()


def _blank_row():
    return {
        "id": "",
        "entry_type": "",
        "date": None,
        "_rank": 0,
        "_created_at": None,
        "_pk": None,
        "supplier_id": None,
        "supplier_code": "",
        "supplier_name": "",
        "reference": "",
        "yarn_intake_id": None,
        "payment_id": None,
        "yarn_name": "",
        "yarn_type": "",
        "yarn_count": "",
        "yarn_quality": "",
        "production_type": "",
        "bags_in": ZERO,
        "cones_per_bag": ZERO,
        "cones_in": ZERO,
        "weight_per_bag_kg": ZERO,
        "weight_kg_in": ZERO,
        "weight_lb_in": ZERO,
        "rate_per_lb": ZERO,
        "purchase_amount": ZERO,
        "payment_method": "",
        "reference_number": "",
        "bank_account_id": None,
        "bank_account_name": "",
        "payment_amount": ZERO,
        "amount_paid": ZERO,
        "amount_due": ZERO,
        "payment_status": "",
        "remaining_bags": ZERO,
        "remaining_cones": ZERO,
        "remaining_weight_kg": ZERO,
        "remaining_weight_lb": ZERO,
        "dispatched_bags": ZERO,
        "balance_bags": ZERO,
        "balance_cones": ZERO,
        "balance_weight_kg": ZERO,
        "balance_weight_lb": ZERO,
        "cumulative_purchases": ZERO,
        "cumulative_paid": ZERO,
        "balance_payables": ZERO,
        "remarks": "",
    }


def _intake_row(yi):
    row = _blank_row()
    bags = _dec(yi.bags)
    cones_per_bag = _dec(yi.cones_per_bag)
    wpb_kg = _dec(yi.weight_per_bag_kg)
    net_kg = _dec(yi.net_weight_kg) or (bags * wpb_kg)
    net_lb = _dec(yi.net_weight_lb) or (net_kg * LB_PER_KG)
    rate_lb = _dec(yi.rate_per_lb)
    tot_rate = _dec(yi.initial_total_rate) or _dec(yi.total_rate) or (net_lb * rate_lb)
    amt_paid = _dec(yi.amount_paid)
    amt_due = _dec(yi.amount_due) if yi.amount_due is not None else max(ZERO, tot_rate - amt_paid)
    status = yi.payment_status or ("Paid" if tot_rate == ZERO else ("Partially Paid" if amt_paid > ZERO else "Unpaid"))

    y_name = yi.yarn_name.name if yi.yarn_name else ""
    y_type = yi.yarn_type.name if yi.yarn_type else ""
    y_count = getattr(yi.yarn_count, "name", "") if yi.yarn_count else ""
    quality = f"{y_name} {y_count} {y_type}".strip()

    row.update(
        {
            "id": f"INT-{yi.id}",
            "entry_type": ENTRY_INTAKE,
            "date": yi.intake_date,
            "_rank": 0,
            "_created_at": yi.created_at,
            "_pk": yi.id,
            "supplier_id": yi.supplier_id,
            "supplier_code": yi.supplier.supplier_code if yi.supplier else "",
            "supplier_name": yi.supplier.supplier_name if yi.supplier else "",
            "reference": yi.set_no or f"Batch #{yi.id}",
            "yarn_intake_id": yi.id,
            "yarn_name": y_name,
            "yarn_type": y_type,
            "yarn_count": y_count,
            "yarn_quality": quality,
            "production_type": yi.production_type or "Self",
            "bags_in": bags,
            "cones_per_bag": cones_per_bag,
            "cones_in": _dec(yi.total_cones) or (bags * cones_per_bag),
            "weight_per_bag_kg": wpb_kg,
            "weight_kg_in": net_kg,
            "weight_lb_in": net_lb,
            "rate_per_lb": rate_lb,
            "purchase_amount": tot_rate,
            "amount_paid": amt_paid,
            "amount_due": amt_due,
            "payment_status": status,
            "remaining_bags": _dec(yi.remaining_bags),
            "remaining_cones": _dec(yi.remaining_cones),
            "remaining_weight_kg": _dec(yi.remaining_weight_kg),
            "remaining_weight_lb": _dec(yi.remaining_weight_lb),
            "dispatched_bags": _dec(yi.outcome_bags),
            "remarks": f"Received {bags} bags of {quality} (Batch {yi.set_no or yi.id})",
        }
    )
    return row


def _payment_row(pm):
    row = _blank_row()
    amt = _dec(pm.amount)
    ref = pm.reference_number or f"Payment #{pm.id}"
    b_name = pm.bank_account.bank_name if pm.bank_account else ""

    row.update(
        {
            "id": f"PAY-{pm.id}",
            "entry_type": ENTRY_PAYMENT,
            "date": pm.payment_date,
            "_rank": 1,
            "_created_at": pm.created_at,
            "_pk": pm.id,
            "supplier_id": pm.supplier_id,
            "supplier_code": pm.supplier.supplier_code if pm.supplier else "",
            "supplier_name": pm.supplier.supplier_name if pm.supplier else "",
            "reference": ref,
            "payment_id": pm.id,
            "yarn_intake_id": pm.yarn_intake_id,
            "payment_method": pm.payment_method,
            "reference_number": pm.reference_number or "",
            "bank_account_id": pm.bank_account_id,
            "bank_account_name": b_name,
            "payment_amount": amt,
            "remarks": pm.notes or f"Paid via {pm.payment_method}{f' ({b_name})' if b_name else ''}",
        }
    )
    return row


def _apply_running_balances(rows):
    """
    Annotate each chronological row with per-supplier running balances.
    Running balances never convert to float and preserve full precision.
    """
    state = {}
    for row in rows:
        bal = state.setdefault(
            row["supplier_id"],
            {
                "bags": ZERO,
                "cones": ZERO,
                "kg": ZERO,
                "lb": ZERO,
                "purchases": ZERO,
                "paid": ZERO,
            },
        )
        if row["entry_type"] == ENTRY_INTAKE:
            bal["bags"] += row["bags_in"]
            bal["cones"] += row["cones_in"]
            bal["kg"] += row["weight_kg_in"]
            bal["lb"] += row["weight_lb_in"]
            bal["purchases"] += row["purchase_amount"]
        elif row["entry_type"] == ENTRY_PAYMENT:
            bal["paid"] += row["payment_amount"]

        row["balance_bags"] = bal["bags"]
        row["balance_cones"] = bal["cones"]
        row["balance_weight_kg"] = bal["kg"]
        row["balance_weight_lb"] = bal["lb"]
        row["cumulative_purchases"] = bal["purchases"]
        row["cumulative_paid"] = bal["paid"]
        row["balance_payables"] = bal["purchases"] - bal["paid"]


def _zero_balance():
    return {
        "balance_bags": ZERO,
        "balance_cones": ZERO,
        "balance_weight_kg": ZERO,
        "balance_weight_lb": ZERO,
        "cumulative_purchases": ZERO,
        "cumulative_paid": ZERO,
        "balance_payables": ZERO,
    }


def _extract_balance(row_or_none):
    if not row_or_none:
        return _zero_balance()
    return {
        "balance_bags": row_or_none.get("balance_bags", ZERO),
        "balance_cones": row_or_none.get("balance_cones", ZERO),
        "balance_weight_kg": row_or_none.get("balance_weight_kg", ZERO),
        "balance_weight_lb": row_or_none.get("balance_weight_lb", ZERO),
        "cumulative_purchases": row_or_none.get("cumulative_purchases", ZERO),
        "cumulative_paid": row_or_none.get("cumulative_paid", ZERO),
        "balance_payables": row_or_none.get("balance_payables", ZERO),
    }


# ── Main Supplier Ledger API ──────────────────────────────────────────────────

def get_main_yarn_supplier_ledger(
    search=None,
    status=None,
    date_from=None,
    date_to=None,
    ordering="supplier_name",
    supplier_type="Yarn",
):
    """
    Returns (supplier_items, aggregate_totals) for the Main Yarn Supplier Ledger.
    Computes exact totals for all yarn suppliers matching the filter.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        sup_qs = Supplier.objects.all()
        if supplier_type:
            sup_qs = sup_qs.filter(Q(supplier_type=supplier_type) | Q(yarn_intakes__isnull=False)).distinct()
        if status:
            sup_qs = sup_qs.filter(status__iexact=status)
        if search:
            sup_qs = sup_qs.filter(
                Q(supplier_name__icontains=search)
                | Q(supplier_code__icontains=search)
                | Q(company_name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(phone__icontains=search)
            )

        suppliers = list(sup_qs.select_related().prefetch_related("bank_accounts"))

        # Build raw chronological rows for these suppliers
        sup_ids = [s.id for s in suppliers]

        intakes_qs = (
            YarnIntake.objects.filter(supplier_id__in=sup_ids)
            .select_related("supplier", "yarn_name", "yarn_type", "yarn_count")
        )
        payments_qs = (
            YarnSupplierPayment.objects.filter(supplier_id__in=sup_ids)
            .select_related("supplier", "bank_account", "yarn_intake")
        )

        all_rows = []
        for yi in intakes_qs:
            all_rows.append(_intake_row(yi))
        for pm in payments_qs:
            all_rows.append(_payment_row(pm))

        # Sort chronologically to compute exact lifetime running balances
        all_rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"] or r["date"], r["_pk"]))
        _apply_running_balances(all_rows)

        # Filter rows by date if requested for window statistics
        window_rows = all_rows
        if date_from:
            window_rows = [r for r in window_rows if r["date"] >= date_from]
        if date_to:
            window_rows = [r for r in window_rows if r["date"] <= date_to]

        # Group stats by supplier
        supplier_stats = {}
        for r in window_rows:
            sid = r["supplier_id"]
            st = supplier_stats.setdefault(
                sid,
                {
                    "bags_received": ZERO,
                    "cones_received": ZERO,
                    "weight_kg_received": ZERO,
                    "weight_lb_received": ZERO,
                    "remaining_bags": ZERO,
                    "remaining_cones": ZERO,
                    "remaining_weight_kg": ZERO,
                    "remaining_weight_lb": ZERO,
                    "purchases": ZERO,
                    "paid": ZERO,
                    "intakes_count": 0,
                    "payments_count": 0,
                },
            )
            if r["entry_type"] == ENTRY_INTAKE:
                st["bags_received"] += r["bags_in"]
                st["cones_received"] += r["cones_in"]
                st["weight_kg_received"] += r["weight_kg_in"]
                st["weight_lb_received"] += r["weight_lb_in"]
                st["remaining_bags"] += r["remaining_bags"]
                st["remaining_cones"] += r["remaining_cones"]
                st["remaining_weight_kg"] += r["remaining_weight_kg"]
                st["remaining_weight_lb"] += r["remaining_weight_lb"]
                st["purchases"] += r["purchase_amount"]
                st["intakes_count"] += 1
            elif r["entry_type"] == ENTRY_PAYMENT:
                st["paid"] += r["payment_amount"]
                st["payments_count"] += 1

        # Current closing balance from all_rows per supplier
        closing_per_sup = {}
        for r in all_rows:
            closing_per_sup[r["supplier_id"]] = r

        results = []
        tot_agg = {
            "total_bags_received": ZERO,
            "total_cones_received": ZERO,
            "total_weight_kg_received": ZERO,
            "total_weight_lb_received": ZERO,
            "total_remaining_bags": ZERO,
            "total_remaining_cones": ZERO,
            "total_remaining_weight_kg": ZERO,
            "total_remaining_weight_lb": ZERO,
            "total_purchases": ZERO,
            "total_paid": ZERO,
            "total_payables": ZERO,
            "suppliers_count": len(suppliers),
            "intakes_count": 0,
            "payments_count": 0,
            "transactions_count": len(window_rows),
        }

        for sup in suppliers:
            st = supplier_stats.get(
                sup.id,
                {
                    "bags_received": ZERO,
                    "cones_received": ZERO,
                    "weight_kg_received": ZERO,
                    "weight_lb_received": ZERO,
                    "remaining_bags": ZERO,
                    "remaining_cones": ZERO,
                    "remaining_weight_kg": ZERO,
                    "remaining_weight_lb": ZERO,
                    "purchases": ZERO,
                    "paid": ZERO,
                    "intakes_count": 0,
                    "payments_count": 0,
                },
            )
            last_row = closing_per_sup.get(sup.id)
            payables = (last_row["balance_payables"] if last_row else ZERO)

            item = {
                "id": sup.id,
                "supplier_id": sup.id,
                "supplier_code": sup.supplier_code,
                "supplier_name": sup.supplier_name,
                "company_name": sup.company_name or "",
                "contact_person": sup.contact_person or "",
                "phone": sup.phone or "",
                "email": sup.email or "",
                "address": sup.address or "",
                "status": sup.status,
                "supplier_type": sup.supplier_type,
                "total_bags_received": st["bags_received"],
                "total_cones_received": st["cones_received"],
                "total_weight_kg_received": st["weight_kg_received"],
                "total_weight_lb_received": st["weight_lb_received"],
                "total_remaining_bags": st["remaining_bags"],
                "total_remaining_cones": st["remaining_cones"],
                "total_remaining_weight_kg": st["remaining_weight_kg"],
                "total_remaining_weight_lb": st["remaining_weight_lb"],
                "total_purchases": st["purchases"],
                "total_paid": st["paid"],
                "total_payables": payables,
                "intakes_count": st["intakes_count"],
                "payments_count": st["payments_count"],
                "transactions_count": st["intakes_count"] + st["payments_count"],
            }
            results.append(item)

            tot_agg["total_bags_received"] += st["bags_received"]
            tot_agg["total_cones_received"] += st["cones_received"]
            tot_agg["total_weight_kg_received"] += st["weight_kg_received"]
            tot_agg["total_weight_lb_received"] += st["weight_lb_received"]
            tot_agg["total_remaining_bags"] += st["remaining_bags"]
            tot_agg["total_remaining_cones"] += st["remaining_cones"]
            tot_agg["total_remaining_weight_kg"] += st["remaining_weight_kg"]
            tot_agg["total_remaining_weight_lb"] += st["remaining_weight_lb"]
            tot_agg["total_purchases"] += st["purchases"]
            tot_agg["total_paid"] += st["paid"]
            tot_agg["total_payables"] += payables
            tot_agg["intakes_count"] += st["intakes_count"]
            tot_agg["payments_count"] += st["payments_count"]

        # Sort results
        reverse = ordering.startswith("-")
        sort_key = ordering.lstrip("-")
        results.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)

        return results, tot_agg


# ── Individual Supplier Detail Ledger API ─────────────────────────────────────

def build_yarn_supplier_ledger(
    supplier_id,
    date_from=None,
    date_to=None,
    entry_type=None,
    search=None,
    descending=False,
):
    """
    Builds the complete chronological ledger for a single supplier.
    Returns:
        (filtered_rows, opening_balance, closing_balance, summary_stats)
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        intakes_qs = (
            YarnIntake.objects.filter(supplier_id=supplier_id)
            .select_related("supplier", "yarn_name", "yarn_type", "yarn_count")
        )
        payments_qs = (
            YarnSupplierPayment.objects.filter(supplier_id=supplier_id)
            .select_related("supplier", "bank_account", "yarn_intake")
        )

        all_rows = []
        for yi in intakes_qs:
            all_rows.append(_intake_row(yi))
        for pm in payments_qs:
            all_rows.append(_payment_row(pm))

        all_rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"] or r["date"], r["_pk"]))
        _apply_running_balances(all_rows)

        # Opening balance before date_from
        opening_balance = _zero_balance()
        if date_from:
            prior_rows = [r for r in all_rows if r["date"] < date_from]
            if prior_rows:
                opening_balance = _extract_balance(prior_rows[-1])

        # Filter within window
        window_rows = all_rows
        if date_from:
            window_rows = [r for r in window_rows if r["date"] >= date_from]
        if date_to:
            window_rows = [r for r in window_rows if r["date"] <= date_to]

        # Filter by entry_type
        if entry_type:
            window_rows = [r for r in window_rows if r["entry_type"] == entry_type]

        # Filter by search
        if search:
            q_lower = search.strip().lower()
            window_rows = [
                r
                for r in window_rows
                if q_lower in str(r.get("reference", "")).lower()
                or q_lower in str(r.get("yarn_quality", "")).lower()
                or q_lower in str(r.get("remarks", "")).lower()
                or q_lower in str(r.get("payment_method", "")).lower()
            ]

        # Closing balance is the balance after all window rows (or full lifetime balance)
        closing_balance = _extract_balance(all_rows[-1]) if all_rows else _zero_balance()

        summary_stats = {
            "total_bags_received": sum((r["bags_in"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_cones_received": sum((r["cones_in"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_weight_kg_received": sum((r["weight_kg_in"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_weight_lb_received": sum((r["weight_lb_in"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_remaining_bags": sum((r["remaining_bags"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_remaining_weight_kg": sum((r["remaining_weight_kg"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_remaining_weight_lb": sum((r["remaining_weight_lb"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_purchases": sum((r["purchase_amount"] for r in window_rows if r["entry_type"] == ENTRY_INTAKE), ZERO),
            "total_paid": sum((r["payment_amount"] for r in window_rows if r["entry_type"] == ENTRY_PAYMENT), ZERO),
            "total_payables": closing_balance["balance_payables"],
            "transactions_count": len(window_rows),
        }

        if descending:
            window_rows = list(reversed(window_rows))

        return window_rows, opening_balance, closing_balance, summary_stats
