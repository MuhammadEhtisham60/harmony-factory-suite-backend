from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome, YarnOutcomeItem
from factory.yarn.yarn_intake.services import recalculate_yarn_intake_stock
from factory.yarn.yarn_intake.serializers import YarnIntakeListSerializer, YarnIntakeDetailSerializer
from factory.yarn.yarn_stock.models import YarnStock, LB_PER_KG
from factory.yarn.yarn_stock.services import recalculate_yarn_stock
from factory.yarn.yarn_stock.serializers import YarnStockListSerializer, YarnStockMinSerializer
from factory.yarn.sizing.models import Sizing, SizingOutcome
from factory.yarn.sizing.services import sync_sizing_outcome_to_intake

User = get_user_model()


class YarnIntakeReturnValuationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        self.supplier = Supplier.objects.create(supplier_name="Test Supplier", status="Active")
        self.yarn_name = YarnName.objects.create(name="Cotton 40s")
        self.yarn_type = YarnType.objects.create(name="Carded")
        self.yarn_count = YarnCount.objects.create(name="40/1")
        self.sizing = Sizing.objects.create(sizing_name="Standard Sizing Unit", status="Active")

    def test_return_bags_adds_price_to_intake_and_recalculates_stock(self):
        # 1. Create YarnIntake: 10 bags, 24 cones/bag, 45.359237 kg/bag (approx 100 lb/bag), rate 500/lb
        intake = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            supplier=self.supplier,
            intake_date=timezone.now().date(),
            bags=10,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.359237"),
            rate_per_lb=Decimal("500.000000"),
            created_by=self.user,
        )

        intake.refresh_from_db()
        stock = intake.stock
        self.assertIsNotNone(stock)
        self.assertEqual(stock.total_boxes, 10)
        self.assertEqual(stock.remaining_bags, 10)
        self.assertEqual(intake.remaining_bags, 10)
        self.assertEqual(intake.remaining_total_rate, intake.total_rate)
        self.assertGreater(intake.total_rate, Decimal("0"))
        initial_stock_total_price = stock.remaining_total_price
        self.assertEqual(initial_stock_total_price, intake.total_rate)

        # 2. Dispatch all 10 bags to Sizing via YarnOutcome
        yo = YarnOutcome.objects.create(
            stock=stock,
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing=self.sizing,
            outcome_bags=10,
            outcome_cones_per_bag=24,
            outcome_weight_per_bag_kg=Decimal("45.359237"),
            outcome_date=timezone.now().date(),
            created_by=self.user,
        )
        YarnOutcomeItem.objects.create(
            yarn_outcome=yo,
            yarn_intake=intake,
            bags=10,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.359237"),
        )
        yo.calculate_outcome_fields()
        yo.save()

        recalculate_yarn_intake_stock(intake)
        stock.refresh_from_db()
        intake.refresh_from_db()

        # Both intake and stock available balances and valuations should now be 0
        self.assertEqual(intake.remaining_bags, 0)
        self.assertEqual(intake.remaining_total_rate, Decimal("0.000000"))
        self.assertEqual(stock.available_boxes, 0)
        self.assertEqual(stock.remaining_bags, 0)
        self.assertEqual(stock.remaining_total_price, Decimal("0.000000"))
        self.assertEqual(stock.price, Decimal("0.000000"))

        # 3. Create SizingOutcome with 8 bags lagat (consumed) and 2 bags returned
        so = SizingOutcome.objects.create(
            yarn_outcome=yo,
            outcome_date=timezone.now().date(),
            total_bags_on_sizing=10,
            bag_packing_cone=24,
            total_cones=240,
            lagat_bags=Decimal("8.000000"),
            lagat_cones=Decimal("192.000000"),
            return_bags=Decimal("2.000000"),
            return_cones=Decimal("0.000000"),
            rate_per_kg=Decimal("15.000000"),
            net_weight_kg=Decimal("362.873896"),
            created_by=self.user,
        )

        intake.refresh_from_db()
        stock.refresh_from_db()

        # Check YarnIntake return price and remaining valuation
        self.assertEqual(intake.return_bags, Decimal("2.000000"))
        self.assertEqual(intake.remaining_bags, 2)
        expected_return_kg = Decimal("2.000000") * Decimal("45.359237")
        expected_return_lb = expected_return_kg * LB_PER_KG
        expected_return_price = (expected_return_lb * Decimal("500.000000")).quantize(Decimal("0.000001"))

        self.assertEqual(intake.return_total_rate, expected_return_price)
        self.assertEqual(intake.remaining_total_rate, expected_return_price)
        # Entry total_rate has ONLY the 2 returned bags price added back, NOT the 10 outcome bags price:
        self.assertEqual(intake.total_rate, expected_return_price)
        self.assertGreater(intake.return_total_rate, Decimal("0.000000"))

        # Check YarnStock all keys recalculation
        self.assertEqual(stock.available_boxes, 2)
        self.assertEqual(stock.remaining_bags, 2)
        self.assertEqual(stock.total_boxes, 2)
        self.assertEqual(stock.total_returned_boxes, Decimal("2.000000"))
        self.assertEqual(stock.total_returned_cones, Decimal("0.000000"))
        self.assertEqual(stock.remaining_total_price, expected_return_price)
        # Stock total_price has ONLY the 2 returned bags price added back, NOT the 10 outcome bags price:
        self.assertEqual(stock.total_price, expected_return_price)
        self.assertGreater(stock.remaining_total_price, Decimal("0.000000"))

        expected_price_per_bag = (expected_return_price / Decimal("2")).quantize(Decimal("0.000001"))
        self.assertEqual(stock.price, expected_price_per_bag)

        # 4. Check Serializers representation
        intake_list_data = YarnIntakeListSerializer(intake).data
        self.assertEqual(Decimal(str(intake_list_data["returnTotalRate"])), expected_return_price)
        self.assertEqual(Decimal(str(intake_list_data["return_total_rate"])), expected_return_price)
        self.assertEqual(Decimal(str(intake_list_data["remainingTotalRate"])), expected_return_price)
        self.assertEqual(Decimal(str(intake_list_data["remaining_total_rate"])), expected_return_price)

        intake_detail_data = YarnIntakeDetailSerializer(intake).data
        self.assertEqual(Decimal(str(intake_detail_data["returnTotalRate"])), expected_return_price)
        self.assertEqual(Decimal(str(intake_detail_data["remainingTotalRate"])), expected_return_price)

        stock_list_data = YarnStockListSerializer(stock).data
        self.assertEqual(Decimal(str(stock_list_data["totalReturnedBoxes"])), Decimal("2.000000"))
        self.assertEqual(Decimal(str(stock_list_data["remainingTotalPrice"])), expected_return_price)
        self.assertEqual(stock_list_data["remainingBags"], 2)

        stock_min_data = YarnStockMinSerializer(stock).data
        self.assertEqual(Decimal(str(stock_min_data["totalReturnedBoxes"])), Decimal("2.000000"))
        self.assertEqual(Decimal(str(stock_min_data["remainingTotalPrice"])), expected_return_price)

        # 5. Update SizingOutcome: return 1 bag instead of 2
        so.return_bags = Decimal("1.000000")
        so.lagat_bags = Decimal("9.000000")
        so.save()

        intake.refresh_from_db()
        stock.refresh_from_db()

        self.assertEqual(intake.return_bags, Decimal("1.000000"))
        self.assertEqual(intake.remaining_bags, 1)
        expected_1_bag_price = (Decimal("1.000000") * Decimal("45.359237") * LB_PER_KG * Decimal("500.000000")).quantize(Decimal("0.000001"))
        self.assertEqual(intake.return_total_rate, expected_1_bag_price)
        self.assertEqual(intake.remaining_total_rate, expected_1_bag_price)

        self.assertEqual(stock.available_boxes, 1)
        self.assertEqual(stock.remaining_bags, 1)
        self.assertEqual(stock.total_returned_boxes, Decimal("1.000000"))
        self.assertEqual(stock.remaining_total_price, expected_1_bag_price)
        self.assertEqual(stock.price, expected_1_bag_price)

        # 6. Delete SizingOutcome: should reset returns and clear valuation
        so.delete()
        intake.refresh_from_db()
        stock.refresh_from_db()

        self.assertEqual(intake.return_bags, Decimal("0.000000"))
        self.assertEqual(intake.remaining_bags, 0)
        self.assertEqual(intake.return_total_rate, Decimal("0.000000"))
        self.assertEqual(intake.remaining_total_rate, Decimal("0.000000"))

        self.assertEqual(stock.available_boxes, 0)
        self.assertEqual(stock.remaining_bags, 0)
        self.assertEqual(stock.total_returned_boxes, Decimal("0.000000"))
        self.assertEqual(stock.remaining_total_price, Decimal("0.000000"))
        self.assertEqual(stock.price, Decimal("0.000000"))
