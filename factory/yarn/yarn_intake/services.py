"""
Stock recalculation service for the Yarn module.

This is the single source of truth for:
  - outcome total aggregation
  - stock validation
  - intake summary recalculation

Never manually increment/decrement denormalized fields.
Always recalculate from actual YarnOutcome rows.
"""

from decimal import Decimal

from django.db.models import Sum

LB_PER_KG = Decimal("2.20462262")


def recalculate_yarn_intake_stock(intake):
    """
    Recalculates YarnIntake denormalized summary fields from
    the actual YarnOutcome records for that intake.

    MUST be called inside transaction.atomic() after any
    YarnOutcome CREATE / UPDATE / DELETE.

    Args:
        intake: YarnIntake instance (already locked with select_for_update)
    """
    agg = intake.outcomes.aggregate(
        total_outcome_bags=Sum("outcome_bags"),
        total_outcome_weight_kg=Sum("outcome_weight_kg"),
        total_outcome_weight_lb=Sum("outcome_weight_lb"),
    )

    total_outcome_bags = agg["total_outcome_bags"] or 0
    total_outcome_weight_kg = agg["total_outcome_weight_kg"] or Decimal("0")
    total_outcome_weight_lb = agg["total_outcome_weight_lb"] or Decimal("0")

    intake.outcome_bags = total_outcome_bags
    intake.outcome_weight_kg = total_outcome_weight_kg
    intake.outcome_weight_lb = total_outcome_weight_lb

    intake.remaining_bags = intake.bags - total_outcome_bags
    intake.remaining_weight_kg = Decimal(str(intake.net_weight_kg)) - total_outcome_weight_kg
    intake.remaining_weight_lb = Decimal(str(intake.net_weight_lb)) - total_outcome_weight_lb

    intake.save(update_fields=[
        "outcome_bags",
        "outcome_weight_kg",
        "outcome_weight_lb",
        "remaining_bags",
        "remaining_weight_kg",
        "remaining_weight_lb",
    ])


def validate_outcome_stock(intake, outcome_bags, exclude_outcome_id=None):
    """
    Validates that adding/updating an outcome does not exceed available stock.

    Args:
        intake:             YarnIntake instance (locked)
        outcome_bags:       int – bags being requested
        exclude_outcome_id: int | None – outcome pk to exclude when updating

    Raises:
        ValueError with field-level error dict if stock is insufficient.
    """
    from django.db.models import Sum

    qs = intake.outcomes.all()
    if exclude_outcome_id is not None:
        qs = qs.exclude(pk=exclude_outcome_id)

    agg = qs.aggregate(existing_bags=Sum("outcome_bags"))
    existing_bags = agg["existing_bags"] or 0

    proposed_total = existing_bags + outcome_bags

    if proposed_total > intake.bags:
        available = intake.bags - existing_bags
        raise ValueError({
            "outcome_bags": [
                f"Requested outcome quantity ({outcome_bags} bags) exceeds available yarn stock. "
                f"Available: {available} bag(s)."
            ]
        })
