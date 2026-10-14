"""
Sizing Ledger service.

The ledger is a read-only, computed view (no table of its own) built from:

  INCOME  (yarn received by a sizing party)  -> YarnOutcome  (outcome_type == "Sizing")
  OUTCOME (set returned / yarn consumed)     -> SizingOutcome

Running balances are kept per sizing party and are accumulated in `Decimal`
with NO rounding, NO quantize() and NO float conversion. A local Decimal
context with a large precision guarantees that chained products/sums of
6-decimal values are never silently truncated by the default 28-digit context.

Yarn consumed on an outcome row (derived, exact):
    weight_kg_out = lagat_bags * yarn_outcome.outcome_weight_per_bag_kg
Sizing charge on an outcome row (derived, exact):
    sizing_charge = rate_per_kg * net_weight_kg      (falls back to stored total_rate)
"""

from datetime import date as date_type
from decimal import Decimal, localcontext

from factory.yarn.yarn_intake.models import YarnOutcome
from factory.yarn.yarn_stock.models import LB_PER_KG

from .models import SizingOutcome

ZERO = Decimal("0")
LEDGER_DECIMAL_PRECISION = 60

ENTRY_INCOME = "income"
ENTRY_OUTCOME = "outcome"
ENTRY_TYPES = (ENTRY_INCOME, ENTRY_OUTCOME)

# Column order for the CSV export: (header, row key)
CSV_COLUMNS = [
    ("Date", "date"),
    ("Type", "entry_type"),
    ("Sizing", "sizing_name"),
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
    ("Sizing Charge", "sizing_charge"),
    ("Balance Bags", "balance_bags"),
    ("Balance Cones", "balance_cones"),
    ("Balance Weight (kg)", "balance_weight_kg"),
    ("Balance Weight (lb)", "balance_weight_lb"),
    ("Charges Payable", "charges_payable"),
    ("Remarks", "remarks"),
]

_NULLABLE_OUTCOME_KEYS = (
    "bags_in", "cones_in", "weight_kg_in", "weight_lb_in",
    "bags_out", "cones_out", "weight_kg_out", "weight_lb_out",
    "set_length_meter", "set_length_gaz", "shortage",
    "net_weight_kg", "rate_per_kg", "sizing_charge",
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
            "id": f"IN-{yo.id}",
            "entry_type": ENTRY_INCOME,
            "date": yo.outcome_date,
            "_rank": 0,
            "_created_at": yo.created_at,
            "_pk": yo.id,
            "sizing_id": yo.sizing_id,
            "sizing_name": yo.sizing.sizing_name if yo.sizing_id else "",
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
        sizing_charge = _dec(so.rate_per_kg) * _dec(so.net_weight_kg)
    else:
        sizing_charge = _dec(so.total_rate)

    ref_parts = []
    if so.set_no:
        ref_parts.append(f"Set #{so.set_no}")
    if so.set_bill:
        ref_parts.append(f"Bill #{so.set_bill}")
    reference = " / ".join(ref_parts) if ref_parts else f"Sizing outcome #{so.id}"

    row = _blank_row()
    row.update(
        {
            "id": f"OUT-{so.id}",
            "entry_type": ENTRY_OUTCOME,
            "date": so.outcome_date,
            "_rank": 1,
            "_created_at": so.created_at,
            "_pk": so.id,
            "sizing_id": yo.sizing_id,
            "sizing_name": yo.sizing.sizing_name if yo.sizing_id else "",
            "reference": reference,
            "yarn_outcome_id": so.yarn_outcome_id,
            "sizing_outcome_id": so.id,
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
            "sizing_charge": sizing_charge,
        }
    )
    return row


def _apply_running_balances(rows):
    """Annotate each (already chronologically sorted) row with per-sizing running balances."""
    state = {}
    for row in rows:
        bal = state.setdefault(
            row["sizing_id"],
            {"bags": ZERO, "cones": ZERO, "kg": ZERO, "charges": ZERO},
        )
        if row["entry_type"] == ENTRY_INCOME:
            bal["bags"] += row["bags_in"]
            bal["cones"] += row["cones_in"]
            bal["kg"] += row["weight_kg_in"]
        else:
            bal["bags"] -= row["bags_out"]
            bal["cones"] -= row["cones_out"]
            bal["kg"] -= row["weight_kg_out"]
            bal["charges"] += row["sizing_charge"]

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
    return {key: row[key] for key in _zero_balance()}


def build_sizing_ledger(
    sizing_id=None,
    date_from=None,
    date_to=None,
    entry_type=None,
    set_no=None,
    search=None,
    descending=False,
):
    """
    Build the filtered ledger.

    Balances are computed over the party's COMPLETE history first and the
    date / type / search filters are applied afterwards, so every returned row
    carries its true cumulative balance (not a balance restarted by a filter).

    Returns (rows, opening_balance). `opening_balance` is only meaningful when
    `sizing_id` is given (otherwise None): it is the party's balance immediately
    before `date_from` (all zeros when there is no earlier activity or no date_from).
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        yarn_qs = YarnOutcome.objects.filter(
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing__isnull=False,
        ).select_related("sizing")
        outcome_qs = SizingOutcome.objects.filter(
            yarn_outcome__sizing__isnull=False
        ).select_related("yarn_outcome", "yarn_outcome__sizing")

        if sizing_id is not None:
            yarn_qs = yarn_qs.filter(sizing_id=sizing_id)
            outcome_qs = outcome_qs.filter(yarn_outcome__sizing_id=sizing_id)

        all_rows = [_income_row(yo) for yo in yarn_qs]
        all_rows += [_outcome_row(so) for so in outcome_qs]
        all_rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"], r["_pk"]))
        _apply_running_balances(all_rows)

        opening_balance = None
        if sizing_id is not None:
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
                    (row["sizing_name"], row["reference"], row["set_no"], row["set_bill"], row["remarks"])
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
    Totals for a filtered set of rows (as returned by `build_sizing_ledger`, any order).

    Closing balance per party = balance carried by that party's last row in the set.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        parties = {}
        for row in sorted(rows, key=lambda r: (r["date"], r["_rank"], r["_created_at"], r["_pk"])):
            p = parties.setdefault(
                row["sizing_id"],
                {
                    "sizing_id": row["sizing_id"],
                    "sizing_name": row["sizing_name"],
                    "entries": 0,
                    "total_bags_in": ZERO,
                    "total_cones_in": ZERO,
                    "total_weight_kg_in": ZERO,
                    "total_weight_lb_in": ZERO,
                    "total_bags_out": ZERO,
                    "total_cones_out": ZERO,
                    "total_weight_kg_out": ZERO,
                    "total_weight_lb_out": ZERO,
                    "total_sizing_charge": ZERO,
                },
            )
            p["entries"] += 1
            if row["entry_type"] == ENTRY_INCOME:
                p["total_bags_in"] += row["bags_in"]
                p["total_cones_in"] += row["cones_in"]
                p["total_weight_kg_in"] += row["weight_kg_in"]
                p["total_weight_lb_in"] += row["weight_lb_in"]
            else:
                p["total_bags_out"] += row["bags_out"]
                p["total_cones_out"] += row["cones_out"]
                p["total_weight_kg_out"] += row["weight_kg_out"]
                p["total_weight_lb_out"] += row["weight_lb_out"]
                p["total_sizing_charge"] += row["sizing_charge"]
            p.update(_balance_of(row))

        party_list = sorted(parties.values(), key=lambda p: (p["sizing_name"], p["sizing_id"]))

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
            "total_sizing_charge": ZERO,
        }
        totals.update(_zero_balance())
        for p in party_list:
            for key in totals:
                totals[key] += p[key]

        return {"totals": totals, "parties": party_list}


def csv_value(value):
    """Render a ledger cell for CSV without rounding Decimals."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return exact_str(value)
    if isinstance(value, date_type):
        return value.isoformat()
    return str(value)
