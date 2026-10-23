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

    raw_prod = (production_type or "").strip()
    if raw_prod.lower() == "conversion":
        prod_type = "Conversion"
    elif raw_prod.lower() == "self":
        prod_type = "Self"
    else:
        prod_type = raw_prod

    return {
        "yarn_name": _resolve_model_instance(yarn_name, YarnName),
        "yarn_type": _resolve_model_instance(yarn_type, YarnType),
        "yarn_count": _resolve_model_instance(yarn_count, YarnCount),
        "production_type": prod_type,
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

    from factory.yarn.sizing.models import SizingOutcome
    from django.db.models import Q

    sizing_return_agg = SizingOutcome.objects.filter(
        Q(yarn_outcome__stock=stock) | Q(yarn_outcome__items__yarn_intake__stock=stock)
    ).distinct().aggregate(
        total_return_bags=Sum("return_bags"),
        total_return_cones=Sum("return_cones"),
    )
    total_return_bags = sizing_return_agg["total_return_bags"] or Decimal("0.000000")
    total_return_cones = sizing_return_agg["total_return_cones"] or Decimal("0.000000")

    avg_weight_per_bag = (total_intake_weight_kg / Decimal(str(total_intake_bags))) if total_intake_bags > 0 else Decimal("0.000000")
    avg_cones_per_bag = (Decimal(str(total_intake_cones)) / Decimal(str(total_intake_bags))) if total_intake_bags > 0 else Decimal("0.000000")
    avg_weight_per_cone = (avg_weight_per_bag / avg_cones_per_bag) if avg_cones_per_bag > 0 else Decimal("0.000000")

    return_weight_kg = (total_return_bags * avg_weight_per_bag) + (total_return_cones * avg_weight_per_cone)
    return_weight_lb = return_weight_kg * LB_PER_KG

    available_boxes = max(0, total_intake_bags - total_outcome_bags + int(total_return_bags))
    available_cones = max(0, total_intake_cones - total_outcome_cones + int(total_return_cones + (total_return_bags * avg_cones_per_bag)))
    available_weight_kg = max(Decimal("0.000000"), total_intake_weight_kg - total_outcome_weight_kg + return_weight_kg)
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
    # Calculate return valuation: sum of return_total_rate from contributing intakes if available, else return_weight_lb * simple_price
    intakes_return_val = stock.intakes.aggregate(s=Sum("return_total_rate"))["s"]
    if intakes_return_val is not None and intakes_return_val > Decimal("0.000000"):
        total_return_value = Decimal(str(intakes_return_val)).quantize(Decimal("0.000001"))
    else:
        total_return_value = (return_weight_lb * simple_price).quantize(Decimal("0.000001"))

    # Remaining total price: valuation of current available inventory in stock
    if available_boxes > 0 and available_weight_kg > Decimal("0.000000"):
        intakes_remaining_val = stock.intakes.aggregate(s=Sum("remaining_total_rate"))["s"]
        if intakes_remaining_val is not None and intakes_remaining_val > Decimal("0.000000"):
            remaining_total_price = Decimal(str(intakes_remaining_val)).quantize(Decimal("0.000001"))
        else:
            remaining_total_price = (available_weight_lb * simple_price).quantize(Decimal("0.000001"))
    else:
        remaining_total_price = Decimal("0.000000")

    # Price per bag: calculated by remaining_total_price divided by remaining_bags
    if available_boxes > 0 and remaining_total_price > Decimal("0.000000"):
        stock_price = (remaining_total_price / Decimal(str(available_boxes))).quantize(Decimal("0.000001"))
    else:
        stock_price = Decimal("0.000000")

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
        "total_return_boxes": total_return_bags,
        "total_return_cones": total_return_cones,
        "total_return_weight_kg": return_weight_kg,
        "total_return_weight_lb": return_weight_lb,
        "total_return_value": total_return_value,
        "available_boxes": available_boxes,
        "available_cones": available_cones,
        "available_weight_kg": available_weight_kg,
        "available_weight_lb": available_weight_lb,
        "price": stock_price,
        "total_price": remaining_total_price,
        "cumulative_intake_price": total_intake_rate,
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


def reconcile_intake_stock_pools():
    """
    Ensures every YarnIntake is assigned to the correct YarnStock pool
    matching (yarn_name, yarn_type, yarn_count, production_type).
    Separates 'Conversion' intakes from 'Self' intakes into their own individual pools.
    """
    from factory.yarn.yarn_intake.models import YarnIntake
    affected_stock_ids = set()

    for intake in YarnIntake.objects.select_related("stock", "yarn_name", "yarn_type", "yarn_count").all():
        raw_prod = (intake.production_type or "").strip()
        if raw_prod.lower() == "conversion" or (not raw_prod and (intake.rate_per_lb or Decimal("0")) == Decimal("0")):
            prod_type = "Conversion"
        elif not raw_prod:
            prod_type = "Self"
        elif raw_prod.lower() == "self":
            prod_type = "Self"
        else:
            prod_type = raw_prod

        if intake.production_type != prod_type:
            intake.production_type = prod_type
            intake.save(update_fields=["production_type"])

        correct_stock = get_or_create_yarn_stock(
            yarn_name=intake.yarn_name,
            yarn_type=intake.yarn_type,
            yarn_count=intake.yarn_count,
            production_type=prod_type,
            user=intake.created_by,
        )

        if not intake.stock_id or intake.stock_id != correct_stock.id:
            if intake.stock_id:
                affected_stock_ids.add(intake.stock_id)
            intake.stock = correct_stock
            intake.save(update_fields=["stock"])
            affected_stock_ids.add(correct_stock.id)
        else:
            affected_stock_ids.add(correct_stock.id)

    # Recalculate all affected stocks
    for sid in affected_stock_ids:
        try:
            st = YarnStock.objects.get(pk=sid)
            recalculate_yarn_stock(st)
        except YarnStock.DoesNotExist:
            pass

    # Clean up empty orphan stocks if any (0 intakes and 0 outcomes)
    YarnStock.objects.filter(intakes__isnull=True, outcomes__isnull=True).delete()


def reconcile_all_stocks():
    """
    Reconciles all YarnStock records in the database, including assigning
    Conversion and Self intakes to their respective pools.
    """
    reconcile_intake_stock_pools()
    count = 0
    for stock in YarnStock.objects.all():
        recalculate_yarn_stock(stock)
        count += 1
    return count
