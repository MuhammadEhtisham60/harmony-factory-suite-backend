"""
Authoritative stock service for the shared YarnStock inventory system.

Single source of truth for:
  - Finding or creating the correct YarnStock pool
  - Calculating ledger totals from intakes and outcomes
  - Stock validation (preventing negative balances and concurrent overdraws)
  - Recalculating YarnStock after intake/outcome create, update, or delete
  - Reconciling stock fields against source records
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Avg, Count, F, ExpressionWrapper, IntegerField
from rest_framework.exceptions import ValidationError

from factory.yarn.yarn_stock.models import YarnStock, LB_PER_KG


def _resolve_model_instance(val, model):
    if isinstance(val, model):
        return val
    if isinstance(val, int):
        return model.objects.get(pk=val)
    if isinstance(val, str) and val.strip():
        if val.strip().isdigit():
            try:
                return model.objects.get(pk=int(val.strip()))
            except model.DoesNotExist:
                pass
        obj, _ = model.objects.get_or_create(name=val.strip())
        return obj
    return None


def normalize_stock_fields(yarn_name, yarn_type, yarn_count, production_type=""):
    """
    Cleans and standardizes stock-identifying attributes, resolving to model instances.
    """
    from factory.yarn.yarn_name.models import YarnName
    from factory.yarn.yarn_type.models import YarnType
    from factory.yarn.yarn_count.models import YarnCount

    return {
        "yarn_name": _resolve_model_instance(yarn_name, YarnName),
        "yarn_type": _resolve_model_instance(yarn_type, YarnType),
        "yarn_count": _resolve_model_instance(yarn_count, YarnCount),
        "production_type": (production_type or "").strip(),
    }


def get_or_create_yarn_stock(yarn_name, yarn_type, yarn_count, production_type="", user=None):
    """
    Finds or creates a YarnStock pool matching the stock-identifying fields.
    Thread-safe and atomic.
    """
    normalized = normalize_stock_fields(yarn_name, yarn_type, yarn_count, production_type)
    with transaction.atomic():
        stock, created = YarnStock.objects.get_or_create(
            yarn_name=normalized["yarn_name"],
            yarn_type=normalized["yarn_type"],
            yarn_count=normalized["yarn_count"],
            production_type=normalized["production_type"],
            defaults={
                "created_by": user if user and user.is_authenticated else None,
                "updated_by": user if user and user.is_authenticated else None,
            }
        )
    return stock


def calculate_stock_aggregates(stock):
    """
    Derives raw intake totals, outcome totals, and available balances
    directly from ledger records.
    """
    intake_agg = stock.intakes.aggregate(
        total_bags=Sum("bags"),
        total_cones=Sum("total_cones"),
        total_weight_kg=Sum("net_weight_kg"),
        total_weight_lb=Sum("net_weight_lb"),
        total_rate=Sum("total_rate"),
    )

    total_intake_bags = intake_agg["total_bags"] or 0
    total_intake_cones = intake_agg["total_cones"] or 0
    total_intake_weight_kg = intake_agg["total_weight_kg"] or Decimal("0.000000")
    total_intake_weight_lb = intake_agg["total_weight_lb"] or Decimal("0.000000")
    total_intake_rate = intake_agg["total_rate"] or Decimal("0.000000")

    outcome_cone_expr = ExpressionWrapper(
        F("outcome_bags") * F("outcome_cones_per_bag"),
        output_field=IntegerField()
    )
    outcome_agg = stock.outcomes.annotate(
        calc_cones=outcome_cone_expr
    ).aggregate(
        total_bags=Sum("outcome_bags"),
        total_cones=Sum("calc_cones"),
        total_weight_kg=Sum("outcome_weight_kg"),
        total_weight_lb=Sum("outcome_weight_lb"),
    )

    total_outcome_bags = outcome_agg["total_bags"] or 0
    total_outcome_cones = outcome_agg["total_cones"] or 0
    total_outcome_weight_kg = outcome_agg["total_weight_kg"] or Decimal("0.000000")
    total_outcome_weight_lb = outcome_agg["total_weight_lb"] or Decimal("0.000000")

    available_boxes = total_intake_bags - total_outcome_bags
    available_cones = total_intake_cones - total_outcome_cones
    available_weight_kg = total_intake_weight_kg - total_outcome_weight_kg
    # Use standard project conversion constant for exact precision
    available_weight_lb = available_weight_kg * LB_PER_KG

    intakes_with_rate = stock.intakes.filter(rate_per_lb__gt=0)
    target_intakes = intakes_with_rate if intakes_with_rate.exists() else stock.intakes
    intake_rates_agg = target_intakes.aggregate(Avg("rate_per_lb"))
    avg_rate = intake_rates_agg["rate_per_lb__avg"]
    if avg_rate is not None:
        simple_price = Decimal(str(avg_rate)).quantize(Decimal("0.000001"))
    else:
        simple_price = Decimal("0.000000")

    # Calculate outcome valuation: outcome weight in lb multiplied by rate per lb in yarn stock
    total_outcome_value = (total_outcome_weight_lb * simple_price).quantize(Decimal("0.000001"))

    # Remaining total price: total price in stock minus outcome valuation
    if available_boxes > 0 and available_weight_kg > Decimal("0.000000"):
        remaining_total_price = total_intake_rate - total_outcome_value
        if remaining_total_price < Decimal("0.000000"):
            remaining_total_price = Decimal("0.000000")
    else:
        remaining_total_price = Decimal("0.000000")

    return {
        "total_intake_bags": total_intake_bags,
        "total_intake_cones": total_intake_cones,
        "total_intake_weight_kg": total_intake_weight_kg,
        "total_intake_weight_lb": total_intake_weight_lb,
        "total_intake_rate": total_intake_rate,
        "total_outcome_bags": total_outcome_bags,
        "total_outcome_cones": total_outcome_cones,
        "total_outcome_weight_kg": total_outcome_weight_kg,
        "total_outcome_weight_lb": total_outcome_weight_lb,
        "available_boxes": available_boxes,
        "available_cones": available_cones,
        "available_weight_kg": available_weight_kg,
        "available_weight_lb": available_weight_lb,
        "price": simple_price,
        "total_price": total_intake_rate,
        "remaining_bags": available_boxes,
        "remaining_cones": available_cones,
        "remaining_weight_kg": available_weight_kg,
        "remaining_weight_lb": available_weight_lb,
        "remaining_total_price": remaining_total_price,
    }


def recalculate_yarn_stock(stock):
    """
    Recalculates and updates the YarnStock row from its actual intakes and outcomes.
    Safe to call within transaction.atomic().
    """
    aggs = calculate_stock_aggregates(stock)

    stock.total_boxes = aggs["available_boxes"]
    stock.cones = aggs["available_cones"]
    stock.total_weight_kg = aggs["available_weight_kg"]
    stock.total_weight_lb = aggs["available_weight_lb"]
    stock.price = aggs["price"]
    stock.total_price = aggs["total_price"]

    stock.remaining_bags = aggs["remaining_bags"]
    stock.remaining_cones = aggs["remaining_cones"]
    stock.remaining_weight_kg = aggs["remaining_weight_kg"]
    stock.remaining_weight_lb = aggs["remaining_weight_lb"]
    stock.remaining_total_price = aggs["remaining_total_price"]

    stock.save(update_fields=[
        "total_boxes",
        "cones",
        "total_weight_kg",
        "total_weight_lb",
        "price",
        "total_price",
        "remaining_bags",
        "remaining_cones",
        "remaining_weight_kg",
        "remaining_weight_lb",
        "remaining_total_price",
        "updated_at",
    ])
    stock.refresh_from_db()
    return stock


def validate_outcome_stock_pool(stock, outcome_bags, outcome_weight_kg=None, exclude_outcome_id=None):
    """
    Validates that a dispatch from this YarnStock pool does not exceed available stock.
    Accounts for other outcomes, and excludes the outcome being edited when updating.

    Raises:
        ValidationError with field-level errors if stock is insufficient.
    """
    intake_agg = stock.intakes.aggregate(
        total_bags=Sum("bags"),
        total_weight_kg=Sum("net_weight_kg")
    )
    total_intake_bags = intake_agg["total_bags"] or 0
    total_intake_kg = intake_agg["total_weight_kg"] or Decimal("0.000000")

    outcomes_qs = stock.outcomes.all()
    if exclude_outcome_id is not None:
        outcomes_qs = outcomes_qs.exclude(pk=exclude_outcome_id)

    outcome_agg = outcomes_qs.aggregate(
        dispatched_bags=Sum("outcome_bags"),
        dispatched_kg=Sum("outcome_weight_kg")
    )
    dispatched_bags = outcome_agg["dispatched_bags"] or 0
    dispatched_kg = outcome_agg["dispatched_kg"] or Decimal("0.000000")

    available_bags = total_intake_bags - dispatched_bags
    available_kg = total_intake_kg - dispatched_kg

    errors = {}
    if outcome_bags > available_bags:
        errors["outcomeBags"] = [
            f"Requested outcome quantity ({outcome_bags} bags) exceeds available stock. "
            f"Available: {available_bags} bag(s)."
        ]

    if outcome_weight_kg is not None and outcome_weight_kg > available_kg:
        errors["outcomeWeightPerBagKg"] = [
            f"Requested outcome weight ({outcome_weight_kg} kg) exceeds available stock. "
            f"Available: {available_kg} kg."
        ]

    if errors:
        raise ValidationError(errors)


def reconcile_all_stocks():
    """
    Reconciles all YarnStock records in the database.
    """
    count = 0
    for stock in YarnStock.objects.all():
        recalculate_yarn_stock(stock)
        count += 1
    return count
