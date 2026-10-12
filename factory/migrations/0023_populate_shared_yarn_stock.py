# Generated for YarnStock data migration

from decimal import Decimal
from django.db import migrations

LB_PER_KG = Decimal("2.20462262")


def populate_yarn_stock_and_link(apps, schema_editor):
    YarnStock = apps.get_model("factory", "YarnStock")
    YarnIntake = apps.get_model("factory", "YarnIntake")
    YarnOutcome = apps.get_model("factory", "YarnOutcome")

    # Step 1: For each YarnIntake, find or create the matching YarnStock pool
    for intake in YarnIntake.objects.all():
        name = (intake.yarn_name or "").strip()
        y_type = (intake.yarn_type or "").strip()
        count = (intake.yarn_count or "").strip()
        prod = (intake.production_type or "").strip()

        stock, _ = YarnStock.objects.get_or_create(
            yarn_name=name,
            yarn_type=y_type,
            yarn_count=count,
            production_type=prod,
            defaults={
                "created_by": intake.created_by,
                "updated_by": intake.updated_by,
            }
        )
        intake.stock = stock
        intake.save(update_fields=["stock"])

    # Step 2: For each YarnOutcome, link to its parent intake's stock pool
    for outcome in YarnOutcome.objects.all():
        if outcome.yarn_intake and outcome.yarn_intake.stock:
            outcome.stock = outcome.yarn_intake.stock
            outcome.save(update_fields=["stock"])

    # Step 3: Recalculate totals for all YarnStock pools
    for stock in YarnStock.objects.all():
        intakes = list(YarnIntake.objects.filter(stock=stock))
        outcomes = list(YarnOutcome.objects.filter(stock=stock))

        total_intake_bags = sum(i.bags for i in intakes)
        total_intake_cones = sum(i.total_cones for i in intakes)
        total_intake_kg = sum(i.net_weight_kg for i in intakes)
        total_intake_rate = sum(i.total_rate for i in intakes)

        total_outcome_bags = sum(o.outcome_bags for o in outcomes)
        total_outcome_cones = sum(o.outcome_bags * o.outcome_cones_per_bag for o in outcomes)
        total_outcome_kg = sum(o.outcome_weight_kg for o in outcomes)

        avail_boxes = total_intake_bags - total_outcome_bags
        avail_cones = total_intake_cones - total_outcome_cones
        avail_kg = total_intake_kg - total_outcome_kg
        avail_lb = (avail_kg * LB_PER_KG).quantize(Decimal("0.001"))

        if total_intake_bags > 0:
            price = (total_intake_rate / Decimal(str(total_intake_bags))).quantize(Decimal("0.01"))
        else:
            price = Decimal("0.00")

        stock.total_boxes = avail_boxes
        stock.cones = avail_cones
        stock.total_weight_kg = avail_kg
        stock.total_weight_lb = avail_lb
        stock.price = price
        stock.save(update_fields=[
            "total_boxes",
            "cones",
            "total_weight_kg",
            "total_weight_lb",
            "price",
        ])


def reverse_populate(apps, schema_editor):
    # Safe reverse: keep intakes and outcomes intact, stock FKs can remain or be cleared
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("factory", "0022_add_yarn_stock_and_relations"),
    ]

    operations = [
        migrations.RunPython(populate_yarn_stock_and_link, reverse_populate),
    ]
