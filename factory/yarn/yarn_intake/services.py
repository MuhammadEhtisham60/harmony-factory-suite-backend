"""
Stock recalculation service for the Yarn module.

Preserves legacy helper functions for YarnIntake while delegating
to the authoritative YarnStock service for shared inventory pools.
"""

from decimal import Decimal
from django.db.models import Sum

from factory.yarn.yarn_stock.models import LB_PER_KG
from factory.yarn.yarn_stock.services import (
    recalculate_yarn_stock,
    validate_outcome_stock_pool,
    get_or_create_yarn_stock,
    calculate_stock_aggregates,
)

__all__ = [
    "LB_PER_KG",
    "recalculate_yarn_intake_stock",
    "validate_outcome_stock",
    "recalculate_yarn_stock",
    "validate_outcome_stock_pool",
    "get_or_create_yarn_stock",
    "calculate_stock_aggregates",
]


def recalculate_yarn_intake_stock(intake):
    """
    Recalculates YarnIntake denormalized summary fields from
    the actual YarnOutcomeItem records (and legacy YarnOutcome records)
    and linked SizingOutcome returns for that intake.
    Also ensures the parent shared YarnStock pool is updated.

    MUST be called inside transaction.atomic() after any
    YarnOutcome CREATE / UPDATE / DELETE or SizingOutcome CREATE / UPDATE / DELETE.

    Args:
        intake: YarnIntake instance (already locked with select_for_update)
    """
    from factory.yarn.sizing.models import SizingOutcome
    from factory.yarn.yarn_intake.models import YarnOutcomeItem
    from django.db.models import Q

    # Outcomes from items (all dispatches are modeled via YarnOutcomeItem)
    item_agg = YarnOutcomeItem.objects.filter(yarn_intake=intake).aggregate(
        total_bags=Sum("bags"),
        total_weight_kg=Sum("weight_kg"),
        total_weight_lb=Sum("weight_lb"),
    )

    total_outcome_bags = item_agg["total_bags"] or 0
    total_outcome_weight_kg = item_agg["total_weight_kg"] or Decimal("0.000000")
    total_outcome_weight_lb = item_agg["total_weight_lb"] or Decimal("0.000000")

    # Find all sizing outcomes linked to outcomes that drew yarn from this intake
    sizing_outcomes = SizingOutcome.objects.filter(
        Q(yarn_outcome__yarn_intakes=intake) | Q(yarn_outcome__items__yarn_intake=intake)
    ).distinct().select_related("yarn_outcome")

    total_return_bags = Decimal("0.000000")
    total_return_cones = Decimal("0.000000")

    for so in sizing_outcomes:
        yo = so.yarn_outcome
        if not yo or not (so.return_bags or so.return_cones):
            continue
        # Calculate ratio of this intake in the yarn outcome
        item_bags = yo.items.filter(yarn_intake=intake).aggregate(s=Sum("bags"))["s"] or 0
        total_yo_bags = yo.outcome_bags or item_bags
        if total_yo_bags > 0:
            ratio = Decimal(str(item_bags)) / Decimal(str(total_yo_bags))
        else:
            ratio = Decimal("1.000000")

        total_return_bags += (so.return_bags or Decimal("0")) * ratio
        total_return_cones += (so.return_cones or Decimal("0")) * ratio

    intake.outcome_bags = total_outcome_bags
    intake.outcome_weight_kg = total_outcome_weight_kg
    intake.outcome_weight_lb = total_outcome_weight_lb
    intake.return_bags = total_return_bags
    intake.return_cones = total_return_cones

    weight_per_bag = Decimal(str(intake.weight_per_bag_kg or 0))
    cones_per_bag = Decimal(str(intake.cones_per_bag or 0))
    weight_per_cone = (weight_per_bag / cones_per_bag) if cones_per_bag > 0 else Decimal("0.000000")

    return_weight_kg = (total_return_bags * weight_per_bag) + (total_return_cones * weight_per_cone)
    return_weight_lb = return_weight_kg * LB_PER_KG

    rate_per_lb = Decimal(str(intake.rate_per_lb or 0))
    return_total_rate = (return_weight_lb * rate_per_lb).quantize(Decimal("0.000001"))
    outcome_total_rate = (total_outcome_weight_lb * rate_per_lb).quantize(Decimal("0.000001"))

    rem_bags_calc = Decimal(str(intake.bags)) - Decimal(str(total_outcome_bags)) + total_return_bags
    intake.remaining_bags = int(rem_bags_calc) if rem_bags_calc >= 0 else 0

    if cones_per_bag > 0:
        total_intake_cones = Decimal(str(intake.bags)) * cones_per_bag
        total_outcome_cones = Decimal(str(total_outcome_bags)) * cones_per_bag
        rem_cones_calc = total_intake_cones - total_outcome_cones + (total_return_bags * cones_per_bag) + total_return_cones
        intake.remaining_cones = int(rem_cones_calc) if rem_cones_calc >= 0 else 0
    else:
        intake.remaining_cones = 0

    rem_weight_kg_calc = Decimal(str(intake.net_weight_kg)) - total_outcome_weight_kg + return_weight_kg
    intake.remaining_weight_kg = rem_weight_kg_calc if rem_weight_kg_calc > Decimal("0.000000") else Decimal("0.000000")

    if intake.remaining_bags > 0 and intake.remaining_weight_kg > Decimal("0.000000"):
        intake.remaining_weight_lb = intake.remaining_weight_kg * LB_PER_KG
        intake.remaining_total_rate = (intake.remaining_weight_lb * rate_per_lb).quantize(Decimal("0.000001"))
    else:
        intake.remaining_weight_lb = Decimal("0.000000")
        intake.remaining_total_rate = Decimal("0.000000")

    intake.return_weight_kg = return_weight_kg
    intake.return_weight_lb = return_weight_lb
    intake.return_total_rate = return_total_rate
    intake.outcome_total_rate = outcome_total_rate
    # Active intake entry valuation: reflects current available inventory in this batch
    intake.total_rate = intake.remaining_total_rate

    intake.save(update_fields=[
        "outcome_bags",
        "outcome_weight_kg",
        "outcome_weight_lb",
        "outcome_total_rate",
        "return_bags",
        "return_cones",
        "return_weight_kg",
        "return_weight_lb",
        "return_total_rate",
        "remaining_bags",
        "remaining_cones",
        "remaining_weight_kg",
        "remaining_weight_lb",
        "remaining_total_rate",
        "total_rate",
    ])

    if intake.stock_id:
        recalculate_yarn_stock(intake.stock)


def validate_outcome_stock(intake, outcome_bags, exclude_outcome_id=None):
    """
    Validates that adding/updating an outcome does not exceed available stock for this intake.

    Args:
        intake:             YarnIntake instance (locked)
        outcome_bags:       int – bags being requested
        exclude_outcome_id: int | None – outcome pk to exclude when updating

    Raises:
        ValueError with field-level error dict if stock is insufficient.
    """
    available = intake.remaining_bags
    if exclude_outcome_id is not None:
        from factory.yarn.yarn_intake.models import YarnOutcomeItem
        item_bags = YarnOutcomeItem.objects.filter(
            yarn_outcome_id=exclude_outcome_id,
            yarn_intake=intake
        ).aggregate(s=Sum("bags"))["s"] or 0
        available += item_bags

    if outcome_bags > available:
        raise ValueError({
            "outcome_bags": [
                f"Requested outcome quantity ({outcome_bags} bags) exceeds available stock for intake '{intake.set_no}'. "
                f"Available: {available} bag(s)."
            ]
        })
