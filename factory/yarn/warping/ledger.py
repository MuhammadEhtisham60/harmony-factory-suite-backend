"""
Warping Ledger service.

The ledger is a read-only, computed view built from:

  INCOME  (yarn received by a warping party)  -> YarnOutcome  (outcome_type == "Warping")
  OUTCOME (set returned / yarn consumed)      -> SizingOutcome (referencing yarn_outcome with outcome_type == "Warping")

Running balances are kept per warping party and are accumulated in Decimal
with NO rounding, NO quantize() and NO float conversion.
"""

from datetime import date as date_type
from decimal import Decimal, localcontext

from django.db.models import Case, When, Sum, Count, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce

from factory.yarn.yarn_intake.models import YarnOutcome
from factory.yarn.yarn_stock.models import LB_PER_KG
from factory.yarn.sizing.models import SizingOutcome

from .models import Warping

ZERO = Decimal("0")
LEDGER_DECIMAL_PRECISION = 60

ENTRY_INCOME = "income"
ENTRY_OUTCOME = "outcome"
ENTRY_TYPES = (ENTRY_INCOME, ENTRY_OUTCOME)

# Column order for the CSV export: (header, row key)
CSV_COLUMNS = [
    ("Date", "date"),
    ("Type", "entry_type"),
    ("Warping", "warping_name"),
    ("Reference", "reference"),
    ("Set No", "set_no"),
    ("Set Bill", "set_bill"),
    ("Bags In", "bags_in"),
    ("Cones In", "cones_in"),
    ("Weight In (kg)", "weight_kg_in"),
    ("Weight In (lb)", "weight_lb_in"),
    ("Bags Out", "bags_out"),
    ("Cones Out", "cones_out"),
    ("Weight Out (kg)", "weight_kg_out"),
    ("Weight Out (lb)", "weight_lb_out"),
    ("Set Length (m)", "set_length_meter"),
    ("Set Length (gaz)", "set_length_gaz"),
    ("Shortage", "shortage"),
    ("Net Weight (kg)", "net_weight_kg"),
    ("Rate / kg", "rate_per_kg"),
    ("Warping Charge", "warping_charge"),
    ("Balance Bags", "balance_bags"),
    ("Balance Cones", "balance_cones"),
    ("Balance Weight (kg)", "balance_weight_kg"),
    ("Balance Weight (lb)", "balance_weight_lb"),
    ("Charges Payable", "charges_payable"),
    ("Remarks", "remarks"),
]

MAIN_CSV_COLUMNS = [
    ("Warping Name", "warping_name"),
    ("Contact Person", "contact_person"),
    ("Phone", "phone_no"),
    ("Email", "email"),
    ("Address", "address"),
    ("Status", "status"),
    ("Bags Sent", "total_boxes_sent"),
    ("Bags Received", "total_boxes_received"),
    ("Bags Balance", "total_boxes_balance"),
    ("Weight Sent (kg)", "total_weight_kg_sent"),
    ("Weight Received (kg)", "total_weight_kg_received"),
    ("Weight Balance (kg)", "total_weight_kg_balance"),
    ("Cones Sent", "total_cones_sent"),
    ("Cones Received", "total_cones_received"),
    ("Cones Balance", "total_cones_balance"),
    ("Total Payables", "total_payables"),
    ("Total Paid", "total_paid"),
    ("Total Charges", "total_charges"),
    ("Transactions Count", "transactions_count"),
]

_NULLABLE_OUTCOME_KEYS = (
    "bags_in", "cones_in", "weight_kg_in", "weight_lb_in",
    "bags_out", "cones_out", "weight_kg_out", "weight_lb_out",
    "set_length_meter", "set_length_gaz", "shortage",
    "net_weight_kg", "rate_per_kg", "warping_charge",
    "amount_paid", "amount_due", "payment_status",
)


def _dec(value):
    """Return `value` as an exact Decimal (None -> 0). Never goes through float."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def exact_str(value):
    """Full-precision plain-notation string for a Decimal (no rounding, no exponent)."""
    if value is None:
        return ""
    return format(value, "f")


def _blank_row():
    row = {key: None for key in _NULLABLE_OUTCOME_KEYS}
    row.update(
        {
            "yarn_outcome_id": None,
            "sizing_outcome_id": None,
            "warping_outcome_id": None,
            "set_no": "",
            "set_bill": "",
            "remarks": "",
        }
    )
    return row


def _income_row(yo):
    cones_per_bag = _dec(yo.outcome_cones_per_bag)
    bags = _dec(yo.outcome_bags)
    weight_kg = bags * _dec(yo.outcome_weight_per_bag_kg)

    row = _blank_row()
    row.update(
        {
            "id": f"OUT-{yo.id}",
            "entry_type": ENTRY_OUTCOME,
            "date": yo.outcome_date,
            "_rank": 0,
            "_created_at": yo.created_at,
            "_pk": yo.id,
            "warping_id": yo.warping_id,
            "warping_name": yo.warping.warping_name if yo.warping_id else "",
            "reference": f"Yarn sent #{yo.id}",
            "yarn_outcome_id": yo.id,
            "remarks": yo.notes or "",
            "bags_in": bags,
            "cones_in": bags * cones_per_bag,
            "weight_kg_in": weight_kg,
            "weight_lb_in": weight_kg * LB_PER_KG,
        }
    )
    return row


def _outcome_row(so):
    yo = so.yarn_outcome
    lagat_bags = _dec(so.lagat_bags)
    weight_kg_out = lagat_bags * _dec(yo.outcome_weight_per_bag_kg)

    if so.rate_per_kg is not None and so.net_weight_kg is not None:
        warping_charge = _dec(so.rate_per_kg) * _dec(so.net_weight_kg)
    else:
        warping_charge = _dec(so.total_rate)

    ref_parts = []
    if so.set_no:
        ref_parts.append(f"Set #{so.set_no}")
    if so.set_bill:
        ref_parts.append(f"Bill #{so.set_bill}")
    reference = " / ".join(ref_parts) if ref_parts else f"Warping outcome #{so.id}"

    row = _blank_row()
    row.update(
        {
            "id": f"IN-{so.id}",
            "entry_type": ENTRY_INCOME,
            "date": so.outcome_date,
            "_rank": 1,
            "_created_at": so.created_at,
            "_pk": so.id,
            "warping_id": yo.warping_id,
            "warping_name": yo.warping.warping_name if yo.warping_id else "",
            "reference": reference,
            "yarn_outcome_id": so.yarn_outcome_id,
            "sizing_outcome_id": so.id,
            "warping_outcome_id": so.id,
            "set_no": so.set_no or "",
            "set_bill": so.set_bill or "",
            "remarks": so.remarks or "",
            "bags_out": lagat_bags,
            "cones_out": _dec(so.lagat_cones),
            "weight_kg_out": weight_kg_out,
            "weight_lb_out": weight_kg_out * LB_PER_KG,
            "set_length_meter": so.set_length_meter,
            "set_length_gaz": so.set_length_gaz,
            "shortage": so.total_set_shortage,
            "net_weight_kg": so.net_weight_kg,
            "rate_per_kg": so.rate_per_kg,
            "warping_charge": warping_charge,
            "amount_paid": so.amount_paid,
            "amount_due": so.amount_due,
            "payment_status": so.payment_status,
        }
    )
    return row


def _apply_running_balances(rows):
    """Annotate each (already chronologically sorted) row with per-warping running balances."""
    state = {}
    for row in rows:
        bal = state.setdefault(
            row["warping_id"],
            {"bags": ZERO, "cones": ZERO, "kg": ZERO, "charges": ZERO},
        )
        if row["entry_type"] == ENTRY_OUTCOME:
            bal["bags"] += row["bags_in"]
            bal["cones"] += row["cones_in"]
            bal["kg"] += row["weight_kg_in"]
        else:
            bal["bags"] -= row["bags_out"]
            bal["cones"] -= row["cones_out"]
            bal["kg"] -= row["weight_kg_out"]
            if row.get("payment_status") == "Paid" or (row.get("amount_due") is not None and _dec(row.get("amount_due")) == ZERO):
                due = ZERO
            elif row.get("amount_paid") and _dec(row.get("amount_paid")) > ZERO:
                due = max(ZERO, row["warping_charge"] - _dec(row.get("amount_paid")))
            else:
                due = row["warping_charge"]
            bal["charges"] += due

        row["balance_bags"] = bal["bags"]
        row["balance_cones"] = bal["cones"]
        row["balance_weight_kg"] = bal["kg"]
        row["balance_weight_lb"] = bal["kg"] * LB_PER_KG
        row["charges_payable"] = bal["charges"]


def _zero_balance():
    return {
        "balance_bags": ZERO,
        "balance_cones": ZERO,
        "balance_weight_kg": ZERO,
        "balance_weight_lb": ZERO,
        "charges_payable": ZERO,
    }


def _balance_of(row):
    return {
        "balance_bags": row["balance_bags"],
        "balance_cones": row["balance_cones"],
        "balance_weight_kg": row["balance_weight_kg"],
        "balance_weight_lb": row["balance_weight_lb"],
        "charges_payable": row["charges_payable"],
    }


def build_warping_ledger(
    warping_id=None,
    date_from=None,
    date_to=None,
    entry_type=None,
    set_no=None,
    search=None,
    descending=False,
):
    """
    Build the filtered warping ledger.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        yarn_qs = YarnOutcome.objects.filter(
            outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            warping__isnull=False,
        ).select_related("warping")
        outcome_qs = SizingOutcome.objects.filter(
            yarn_outcome__outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            yarn_outcome__warping__isnull=False,
        ).select_related("yarn_outcome", "yarn_outcome__warping")

        if warping_id is not None:
            yarn_qs = yarn_qs.filter(warping_id=warping_id)
            outcome_qs = outcome_qs.filter(yarn_outcome__warping_id=warping_id)

        all_rows = [_income_row(yo) for yo in yarn_qs]
        all_rows += [_outcome_row(so) for so in outcome_qs]
        all_rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"], r["_pk"]))
        _apply_running_balances(all_rows)

        opening_balance = None
        if warping_id is not None:
            opening_balance = _zero_balance()
            if date_from is not None:
                earlier = [r for r in all_rows if r["date"] < date_from]
                if earlier:
                    opening_balance = _balance_of(earlier[-1])

        needle = search.strip().lower() if search else None
        set_needle = set_no.strip().lower() if set_no else None

        def keep(row):
            if date_from is not None and row["date"] < date_from:
                return False
            if date_to is not None and row["date"] > date_to:
                return False
            if entry_type and row["entry_type"] != entry_type:
                return False
            if set_needle and set_needle not in row["set_no"].lower():
                return False
            if needle:
                haystack = " ".join(
                    (row["warping_name"], row["reference"], row["set_no"], row["set_bill"], row["remarks"])
                ).lower()
                if needle not in haystack:
                    return False
            return True

        rows = [r for r in all_rows if keep(r)]
        if descending:
            rows.reverse()
        return rows, opening_balance


def summarize_ledger(rows):
    """
    Totals for a filtered set of rows.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        parties = {}
        for row in sorted(rows, key=lambda r: (r["date"], r["_rank"], r["_created_at"], r["_pk"])):
            p = parties.setdefault(
                row["warping_id"],
                {
                    "warping_id": row["warping_id"],
                    "warping_name": row["warping_name"],
                    "entries": 0,
                    "total_bags_in": ZERO,
                    "total_cones_in": ZERO,
                    "total_weight_kg_in": ZERO,
                    "total_weight_lb_in": ZERO,
                    "total_bags_out": ZERO,
                    "total_cones_out": ZERO,
                    "total_weight_kg_out": ZERO,
                    "total_weight_lb_out": ZERO,
                    "total_warping_charge": ZERO,
                    "total_amount_paid": ZERO,
                    "total_payables": ZERO,
                },
            )
            p["entries"] += 1
            if row["entry_type"] == ENTRY_OUTCOME:
                p["total_bags_in"] += row["bags_in"]
                p["total_cones_in"] += row["cones_in"]
                p["total_weight_kg_in"] += row["weight_kg_in"]
                p["total_weight_lb_in"] += row["weight_lb_in"]
            else:
                p["total_bags_out"] += row["bags_out"]
                p["total_cones_out"] += row["cones_out"]
                p["total_weight_kg_out"] += row["weight_kg_out"]
                p["total_weight_lb_out"] += row["weight_lb_out"]
                p["total_warping_charge"] += row["warping_charge"]
                p["total_amount_paid"] += _dec(row.get("amount_paid"))
                if row.get("payment_status") == "Paid" or (row.get("amount_due") is not None and _dec(row.get("amount_due")) == ZERO):
                    due = ZERO
                elif row.get("amount_paid") and _dec(row.get("amount_paid")) > ZERO:
                    due = max(ZERO, row["warping_charge"] - _dec(row.get("amount_paid")))
                else:
                    due = row["warping_charge"]
                p["total_payables"] += due
            p.update(_balance_of(row))

        party_list = sorted(parties.values(), key=lambda p: (p["warping_name"], p["warping_id"]))

        totals = {
            "entries": 0,
            "total_bags_in": ZERO,
            "total_cones_in": ZERO,
            "total_weight_kg_in": ZERO,
            "total_weight_lb_in": ZERO,
            "total_bags_out": ZERO,
            "total_cones_out": ZERO,
            "total_weight_kg_out": ZERO,
            "total_weight_lb_out": ZERO,
            "total_warping_charge": ZERO,
            "total_amount_paid": ZERO,
            "total_payables": ZERO,
        }
        totals.update(_zero_balance())
        for p in party_list:
            for key in totals:
                totals[key] += p[key]

        return {"totals": totals, "parties": party_list}


def csv_value(row, key):
    val = row.get(key)
    if val is None:
        return ""
    if isinstance(val, date_type):
        return val.isoformat()
    if isinstance(val, Decimal):
        return exact_str(val)
    return str(val)


def get_main_warping_ledger(ordering="warping_name", status=None, date_from=None, date_to=None, search=None):
    """
    Computes summary counters for all Warping units with aggregate totals.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        warping_qs = Warping.objects.all()
        if status:
            warping_qs = warping_qs.filter(status=status)
        if search:
            needle = search.strip()
            warping_qs = warping_qs.filter(
                Q(warping_name__icontains=needle)
                | Q(contact_person__icontains=needle)
                | Q(phone_no__icontains=needle)
                | Q(email__icontains=needle)
                | Q(address__icontains=needle)
            )

        warping_list = list(warping_qs)
        warping_ids = [w.id for w in warping_list]

        if not warping_ids:
            empty_totals = {
                "total_payables": ZERO,
                "total_charges": ZERO,
                "total_paid": ZERO,
                "total_boxes_sent": ZERO,
                "total_boxes_received": ZERO,
                "total_boxes_balance": ZERO,
                "total_weight_kg_sent": ZERO,
                "total_weight_kg_received": ZERO,
                "total_weight_kg_balance": ZERO,
                "total_cones_sent": ZERO,
                "total_cones_received": ZERO,
                "total_cones_balance": ZERO,
                "total_warpings_count": 0,
            }
            return [], empty_totals

        yo_qs = YarnOutcome.objects.filter(
            outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            warping_id__in=warping_ids,
        )
        so_qs = SizingOutcome.objects.filter(
            yarn_outcome__outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            yarn_outcome__warping_id__in=warping_ids,
        )

        if date_from is not None:
            yo_qs = yo_qs.filter(outcome_date__gte=date_from)
            so_qs = so_qs.filter(outcome_date__gte=date_from)
        if date_to is not None:
            yo_qs = yo_qs.filter(outcome_date__lte=date_to)
            so_qs = so_qs.filter(outcome_date__lte=date_to)

        due_expr = Case(
            When(amount_due__isnull=False, then=F("amount_due")),
            default=Coalesce(F("total_rate"), Value(Decimal("0"))) - Coalesce(F("amount_paid"), Value(Decimal("0"))),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        )

        # 1. Independent aggregation for YarnOutcome (Boxes sent to warping)
        yo_grouped = (
            yo_qs.values("warping_id")
            .annotate(
                boxes_sent=Coalesce(Sum("outcome_bags"), Value(0)),
                cones_sent=Coalesce(Sum(F("outcome_bags") * F("outcome_cones_per_bag")), Value(0)),
                weight_kg_sent=Coalesce(Sum("outcome_weight_kg"), Value(Decimal("0"))),
                weight_lb_sent=Coalesce(Sum("outcome_weight_lb"), Value(Decimal("0"))),
                tx_count=Count("id"),
            )
        )
        sent_map = {item["warping_id"]: item for item in yo_grouped}

        # 2. Independent aggregation for outcomes returned from warping
        so_grouped = (
            so_qs.values("yarn_outcome__warping_id")
            .annotate(
                boxes_recv=Coalesce(Sum("lagat_bags"), Value(Decimal("0"))),
                cones_recv=Coalesce(Sum("lagat_cones"), Value(Decimal("0"))),
                net_weight_kg_recv=Coalesce(Sum("net_weight_kg"), Value(Decimal("0"))),
                payables=Coalesce(Sum(due_expr), Value(Decimal("0"))),
                charges=Coalesce(Sum("total_rate"), Value(Decimal("0"))),
                paid=Coalesce(Sum("amount_paid"), Value(Decimal("0"))),
                tx_count=Count("id"),
            )
        )
        recv_map = {item["yarn_outcome__warping_id"]: item for item in so_grouped}

        # 3. Overall aggregate totals across the entire filtered dataset
        overall_sent = yo_qs.aggregate(
            boxes_sent=Coalesce(Sum("outcome_bags"), Value(0)),
            cones_sent=Coalesce(Sum(F("outcome_bags") * F("outcome_cones_per_bag")), Value(0)),
            weight_kg_sent=Coalesce(Sum("outcome_weight_kg"), Value(Decimal("0"))),
            weight_lb_sent=Coalesce(Sum("outcome_weight_lb"), Value(Decimal("0"))),
        )
        overall_recv = so_qs.aggregate(
            boxes_recv=Coalesce(Sum("lagat_bags"), Value(Decimal("0"))),
            cones_recv=Coalesce(Sum("lagat_cones"), Value(Decimal("0"))),
            net_weight_kg_recv=Coalesce(Sum("net_weight_kg"), Value(Decimal("0"))),
            payables=Coalesce(Sum(due_expr), Value(Decimal("0"))),
            charges=Coalesce(Sum("total_rate"), Value(Decimal("0"))),
            paid=Coalesce(Sum("amount_paid"), Value(Decimal("0"))),
        )

        tot_boxes_sent = _dec(overall_sent["boxes_sent"])
        tot_boxes_recv = _dec(overall_recv["boxes_recv"])
        tot_boxes_bal = tot_boxes_sent - tot_boxes_recv
        tot_payables = _dec(overall_recv["payables"])
        tot_charges = _dec(overall_recv["charges"])
        tot_paid = _dec(overall_recv["paid"])

        tot_cones_sent = _dec(overall_sent["cones_sent"])
        tot_cones_recv = _dec(overall_recv["cones_recv"])
        tot_cones_bal = tot_cones_sent - tot_cones_recv

        tot_weight_kg_sent = _dec(overall_sent["weight_kg_sent"])
        tot_weight_kg_recv = _dec(overall_recv["net_weight_kg_recv"])
        tot_weight_kg_bal = tot_weight_kg_sent - tot_weight_kg_recv

        aggregate_totals = {
            "total_payables": tot_payables,
            "total_charges": tot_charges,
            "total_paid": tot_paid,
            "total_boxes_sent": tot_boxes_sent,
            "total_boxes_received": tot_boxes_recv,
            "total_boxes_balance": tot_boxes_bal,
            "total_weight_kg_sent": tot_weight_kg_sent,
            "total_weight_kg_received": tot_weight_kg_recv,
            "total_weight_kg_balance": tot_weight_kg_bal,
            "total_cones_sent": tot_cones_sent,
            "total_cones_received": tot_cones_recv,
            "total_cones_balance": tot_cones_bal,
            "total_warpings_count": len(warping_list),
        }

        # 4. Assemble per-warping items
        warping_items = []
        for w in warping_list:
            w_id = w.id
            w_sent = sent_map.get(w_id, {})
            w_recv = recv_map.get(w_id, {})

            b_sent = _dec(w_sent.get("boxes_sent", ZERO))
            b_recv = _dec(w_recv.get("boxes_recv", ZERO))
            b_bal = b_sent - b_recv

            pay = _dec(w_recv.get("payables", ZERO))
            charges = _dec(w_recv.get("charges", ZERO))
            paid = _dec(w_recv.get("paid", ZERO))

            c_sent = _dec(w_sent.get("cones_sent", ZERO))
            c_recv = _dec(w_recv.get("cones_recv", ZERO))
            c_bal = c_sent - c_recv

            w_sent_kg = _dec(w_sent.get("weight_kg_sent", ZERO))
            w_recv_kg = _dec(w_recv.get("net_weight_kg_recv", ZERO))
            w_bal_kg = w_sent_kg - w_recv_kg

            tx_count = w_sent.get("tx_count", 0) + w_recv.get("tx_count", 0)

            warping_items.append({
                "id": w.id,
                "warping_name": w.warping_name,
                "contact_person": w.contact_person,
                "phone_no": w.phone_no,
                "email": w.email,
                "address": w.address,
                "status": w.status,
                "notes": w.notes,
                "total_boxes_sent": b_sent,
                "total_boxes_received": b_recv,
                "total_boxes_balance": b_bal,
                "total_payables": pay,
                "total_charges": charges,
                "total_paid": paid,
                "total_weight_kg_sent": w_sent_kg,
                "total_weight_kg_received": w_recv_kg,
                "total_weight_kg_balance": w_bal_kg,
                "total_cones_sent": c_sent,
                "total_cones_received": c_recv,
                "total_cones_balance": c_bal,
                "transactions_count": tx_count,
                "created_at": w.created_at,
                "updated_at": w.updated_at,
            })

        # 5. Handle ordering
        rev = False
        sort_key = ordering or "warping_name"
        if sort_key.startswith("-"):
            rev = True
            sort_key = sort_key[1:]

        valid_sort_keys = {
            "warping_name": lambda x: (x["warping_name"] or "").lower(),
            "status": lambda x: (x["status"] or "").lower(),
            "created_at": lambda x: x["created_at"],
            "total_boxes_sent": lambda x: x["total_boxes_sent"],
            "total_boxes_received": lambda x: x["total_boxes_received"],
            "total_boxes_balance": lambda x: x["total_boxes_balance"],
            "total_payables": lambda x: x["total_payables"],
            "total_charges": lambda x: x["total_charges"],
            "total_paid": lambda x: x["total_paid"],
            "transactions_count": lambda x: x["transactions_count"],
        }
        key_func = valid_sort_keys.get(sort_key, valid_sort_keys["warping_name"])
        warping_items.sort(key=key_func, reverse=rev)

        return warping_items, aggregate_totals


def get_individual_warping_ledger_summary(warping_id, date_from=None, date_to=None):
    """
    Computes summary counters specifically for one warping unit/party.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        due_expr = Case(
            When(amount_due__isnull=False, then=F("amount_due")),
            default=Coalesce(F("total_rate"), Value(Decimal("0"))) - Coalesce(F("amount_paid"), Value(Decimal("0"))),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        )

        yo_qs = YarnOutcome.objects.filter(
            outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            warping_id=warping_id,
        )
        so_qs = SizingOutcome.objects.filter(
            yarn_outcome__outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            yarn_outcome__warping_id=warping_id,
        )

        if date_from is not None:
            yo_qs = yo_qs.filter(outcome_date__gte=date_from)
            so_qs = so_qs.filter(outcome_date__gte=date_from)
        if date_to is not None:
            yo_qs = yo_qs.filter(outcome_date__lte=date_to)
            so_qs = so_qs.filter(outcome_date__lte=date_to)

        sent = yo_qs.aggregate(
            boxes_sent=Coalesce(Sum("outcome_bags"), Value(0)),
            cones_sent=Coalesce(Sum(F("outcome_bags") * F("outcome_cones_per_bag")), Value(0)),
            weight_kg_sent=Coalesce(Sum("outcome_weight_kg"), Value(Decimal("0"))),
            weight_lb_sent=Coalesce(Sum("outcome_weight_lb"), Value(Decimal("0"))),
        )
        recv = so_qs.aggregate(
            boxes_recv=Coalesce(Sum("lagat_bags"), Value(Decimal("0"))),
            cones_recv=Coalesce(Sum("lagat_cones"), Value(Decimal("0"))),
            net_weight_kg_recv=Coalesce(Sum("net_weight_kg"), Value(Decimal("0"))),
            payables=Coalesce(Sum(due_expr), Value(Decimal("0"))),
            charges=Coalesce(Sum("total_rate"), Value(Decimal("0"))),
            paid=Coalesce(Sum("amount_paid"), Value(Decimal("0"))),
        )

        tot_boxes_sent = _dec(sent["boxes_sent"])
        tot_boxes_recv = _dec(recv["boxes_recv"])
        tot_boxes_bal = tot_boxes_sent - tot_boxes_recv
        tot_payables = _dec(recv["payables"])
        tot_charges = _dec(recv["charges"])
        tot_paid = _dec(recv["paid"])

        tot_cones_sent = _dec(sent["cones_sent"])
        tot_cones_recv = _dec(recv["cones_recv"])
        tot_cones_bal = tot_cones_sent - tot_cones_recv

        tot_weight_kg_sent = _dec(sent["weight_kg_sent"])
        tot_weight_kg_recv = _dec(recv["net_weight_kg_recv"])
        tot_weight_kg_bal = tot_weight_kg_sent - tot_weight_kg_recv

        return {
            "total_payables": tot_payables,
            "total_charges": tot_charges,
            "total_paid": tot_paid,
            "total_boxes_sent": tot_boxes_sent,
            "total_boxes_received": tot_boxes_recv,
            "total_boxes_balance": tot_boxes_bal,
            "total_weight_kg_sent": tot_weight_kg_sent,
            "total_weight_kg_received": tot_weight_kg_recv,
            "total_weight_kg_balance": tot_weight_kg_bal,
            "total_cones_sent": tot_cones_sent,
            "total_cones_received": tot_cones_recv,
            "total_cones_balance": tot_cones_bal,
        }
