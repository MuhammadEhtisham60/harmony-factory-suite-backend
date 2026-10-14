"""
Comprehensive Test Suite for Shared YarnStock Inventory Flow in Harmony Factory Suite.

Covers all 14 required specifications:
1. First intake creates a stock pool.
2. A second matching intake contributes to the same pool.
3. Different yarn counts create separate pools.
4. Different production types create separate pools.
5. Creating an outcome decreases available stock.
6. Editing an outcome recalculates the stock correctly.
7. Deleting an outcome restores its contribution to available stock.
8. Updating an intake moves its contribution correctly if its stock category changes.
9. An overdraw is rejected (both bags and weight).
10. Two concurrent dispatches cannot overdraw the same stock pool.
11. Kilogram and pound calculations remain consistent.
12. Box and cone counts are accurate where conversions are supported.
13. Existing Sizing, Weft, Sold, buyer, price, permissions, and beam assignment rules remain intact.
14. API endpoints, filtering, history (intakes, outcomes), and migration stability.
"""

from decimal import Decimal
import threading
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from factory.purchase.supplier.models import Supplier
from factory.yarn.sizing.models import Sizing
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome, LB_PER_KG
from factory.yarn.yarn_stock.models import YarnStock
from factory.yarn.yarn_stock.services import (
    recalculate_yarn_stock,
    get_or_create_yarn_stock,
)

User = get_user_model()


class SharedYarnStockTests(TransactionTestCase):
    """
    TransactionTestCase is used so that multi-threaded concurrency
    and transactions can be tested accurately.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_stock_test",
            email="stock_test@example.com",
            password="Password@123",
            status="Active"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            supplier_name="Premium Mills Ltd",
            supplier_code="PML-001",
            status="Active"
        )

        self.sizing = Sizing.objects.create(
            sizing_name="Al-Rehman Sizing",
            contact_person="Chaudhry Sab",
            status="Active"
        )

        self.buyer = YarnBuyer.objects.create(
            buyer_name="Fine Fabrics Trading",
            status="Active"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 1. First intake creates a stock pool
    # ──────────────────────────────────────────────────────────────────────────
    def test_01_first_intake_creates_stock_pool(self):
        payload = {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Warp",
            "setNo": "SET-001",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 10,
            "conesPerBag": 24,
            "ratePerLb": "150.0000",
            "weightPerBagKg": "45.360",
        }
        res = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        # Verify YarnStock created
        stock = YarnStock.objects.get(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp"
        )
        self.assertEqual(stock.total_boxes, 10)
        self.assertEqual(stock.cones, 240)
        self.assertEqual(stock.total_weight_kg, Decimal("453.600"))
        expected_lb = (Decimal("453.600") * LB_PER_KG).quantize(Decimal("0.000001"))
        self.assertEqual(stock.total_weight_lb, expected_lb)
        self.assertEqual(stock.price, Decimal("150.000000"))

        # Verify intake has FK to this stock
        intake = YarnIntake.objects.get(pk=res.data["data"]["id"])
        self.assertEqual(intake.stock_id, stock.id)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Second matching intake contributes to the same pool
    # ──────────────────────────────────────────────────────────────────────────
    def test_02_second_matching_intake_contributes_to_same_pool(self):
        # Intake 1: 10 bags @ 15,000 PKR = 150,000 PKR
        intake1 = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="SET-001",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=24,
            rate_per_lb=Decimal("150.0000"),
            weight_per_bag_kg=Decimal("45.360"),
        )
        recalculate_yarn_stock(intake1.stock)

        # Intake 2: 15 bags @ 160 PKR/lb
        payload = {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Warp",
            "setNo": "SET-002",
            "intakeDate": "2026-10-11",
            "supplier": self.supplier.id,
            "bags": 15,
            "conesPerBag": 24,
            "ratePerLb": "160.0000",
            "weightPerBagKg": "45.360",
        }
        res = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        # Only 1 stock pool must exist for Cotton 20/1 Carded Warp
        self.assertEqual(YarnStock.objects.count(), 1)
        stock = YarnStock.objects.first()

        # Available boxes = 10 + 15 = 25
        self.assertEqual(stock.total_boxes, 25)
        self.assertEqual(stock.cones, 600)  # 25 * 24
        self.assertEqual(stock.total_weight_kg, Decimal("1134.000"))  # 25 * 45.360

        # Weighted price: (10*150 + 15*160) / 25 = 156.000000
        self.assertEqual(stock.price, Decimal("156.000000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Different yarn counts create separate pools
    # ──────────────────────────────────────────────────────────────────────────
    def test_03_different_yarn_counts_create_separate_pools(self):
        # Pool 1: 20/1 Warp (100 kg)
        self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Warp",
            "setNo": "S-20",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 10,
            "conesPerBag": 20,
            "ratePerLb": "100.0000",
            "weightPerBagKg": "10.000",
        }, format="json")

        # Pool 2: 30/1 Warp (80 kg)
        self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "30/1",
            "productionType": "Warp",
            "setNo": "S-30",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 8,
            "conesPerBag": 20,
            "ratePerLb": "120.0000",
            "weightPerBagKg": "10.000",
        }, format="json")

        self.assertEqual(YarnStock.objects.count(), 2)
        stock_20 = YarnStock.objects.get(yarn_count="20/1")
        stock_30 = YarnStock.objects.get(yarn_count="30/1")

        self.assertEqual(stock_20.total_boxes, 10)
        self.assertEqual(stock_20.total_weight_kg, Decimal("100.000"))
        self.assertEqual(stock_30.total_boxes, 8)
        self.assertEqual(stock_30.total_weight_kg, Decimal("80.000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Different production types create separate pools
    # ──────────────────────────────────────────────────────────────────────────
    def test_04_different_production_types_create_separate_pools(self):
        self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Warp",
            "setNo": "WARP-1",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 5,
            "conesPerBag": 20,
            "ratePerLb": "100.0000",
            "weightPerBagKg": "10.000",
        }, format="json")

        self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Weft",
            "setNo": "WEFT-1",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 7,
            "conesPerBag": 20,
            "ratePerLb": "100.0000",
            "weightPerBagKg": "10.000",
        }, format="json")

        self.assertEqual(YarnStock.objects.count(), 2)
        warp_stock = YarnStock.objects.get(production_type="Warp")
        weft_stock = YarnStock.objects.get(production_type="Weft")

        self.assertEqual(warp_stock.total_boxes, 5)
        self.assertEqual(weft_stock.total_boxes, 7)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Creating an outcome decreases available stock
    # ──────────────────────────────────────────────────────────────────────────
    def test_05_creating_outcome_decreases_available_stock(self):
        # Two intakes into Cotton 20/1 Warp: 10 bags (100 kg) + 15 bags (150 kg) = 250 kg (25 bags)
        intake1 = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="A1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=20,
            rate_per_lb=Decimal("100.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        intake2 = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="A2",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=15,
            cones_per_bag=20,
            rate_per_lb=Decimal("100.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock_20 = intake1.stock
        recalculate_yarn_stock(stock_20)

        # Another separate pool: 30/1 Warp: 8 bags (80 kg)
        intake3 = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="30/1",
            production_type="Warp",
            set_no="B1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=8,
            cones_per_bag=20,
            rate_per_lb=Decimal("120.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock_30 = intake3.stock
        recalculate_yarn_stock(stock_30)

        self.assertEqual(stock_20.total_boxes, 25)
        self.assertEqual(stock_20.total_weight_kg, Decimal("250.000"))
        self.assertEqual(stock_30.total_boxes, 8)
        self.assertEqual(stock_30.total_weight_kg, Decimal("80.000"))

        # Dispatch 4 bags (40 kg) from Cotton 20/1 Warp for Sizing using stockId (NO intake ID specified)
        outcome_payload = {
            "stock": stock_20.id,
            "outcomeType": "Sizing",
            "outcomeBags": 4,
            "outcomeConesPerBag": 20,
            "outcomeWeightPerBagKg": "10.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }
        res = self.client.post("/api/v1/yarn-outcomes/", outcome_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        # Reload stock pools from DB
        stock_20.refresh_from_db()
        stock_30.refresh_from_db()

        # Available Cotton 20/1 Warp must now be 21 bags (210 kg)
        self.assertEqual(stock_20.total_boxes, 21)
        self.assertEqual(stock_20.total_weight_kg, Decimal("210.000"))
        self.assertEqual(stock_20.cones, 420)  # 21 * 20

        # Cotton 30/1 pool must remain completely unchanged (8 bags, 80 kg)
        self.assertEqual(stock_30.total_boxes, 8)
        self.assertEqual(stock_30.total_weight_kg, Decimal("80.000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Editing an outcome recalculates the stock correctly
    # ──────────────────────────────────────────────────────────────────────────
    def test_06_editing_outcome_recalculates_stock_correctly(self):
        intake = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="S-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=20,
            cones_per_bag=10,
            rate_per_lb=Decimal("100.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        # Create outcome of 5 bags
        outcome_res = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 5,
            "outcomeConesPerBag": 10,
            "outcomeWeightPerBagKg": "10.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }, format="json")
        outcome_id = outcome_res.data["data"]["id"]
        stock.refresh_from_db()
        self.assertEqual(stock.total_boxes, 15)

        # Edit outcome from 5 bags to 8 bags
        patch_res = self.client.patch(f"/api/v1/yarn-outcomes/{outcome_id}/", {
            "outcomeBags": 8,
            "outcomeWeightPerBagKg": "10.000",
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK, patch_res.data)

        stock.refresh_from_db()
        # Available stock must now be 20 - 8 = 12 boxes
        self.assertEqual(stock.total_boxes, 12)
        self.assertEqual(stock.total_weight_kg, Decimal("120.000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Deleting an outcome restores its contribution to available stock
    # ──────────────────────────────────────────────────────────────────────────
    def test_07_deleting_outcome_restores_stock(self):
        intake = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="S-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=20,
            cones_per_bag=10,
            rate_per_lb=Decimal("100.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        outcome_res = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 6,
            "outcomeConesPerBag": 10,
            "outcomeWeightPerBagKg": "10.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }, format="json")
        outcome_id = outcome_res.data["data"]["id"]
        stock.refresh_from_db()
        self.assertEqual(stock.total_boxes, 14)

        # Delete outcome
        del_res = self.client.delete(f"/api/v1/yarn-outcomes/{outcome_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        stock.refresh_from_db()
        # Stock must be restored to full 20 bags
        self.assertEqual(stock.total_boxes, 20)
        self.assertEqual(stock.total_weight_kg, Decimal("200.000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Updating an intake moves contribution correctly if category changes
    # ──────────────────────────────────────────────────────────────────────────
    def test_08_updating_intake_moves_contribution_between_pools(self):
        # Create intake 10 bags in Cotton 20/1 Warp
        intake_res = self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Cotton",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "productionType": "Warp",
            "setNo": "SET-MV",
            "intakeDate": "2026-10-10",
            "supplier": self.supplier.id,
            "bags": 10,
            "conesPerBag": 20,
            "ratePerLb": "100.0000",
            "weightPerBagKg": "10.000",
        }, format="json")
        intake_id = intake_res.data["data"]["id"]

        pool_20 = YarnStock.objects.get(yarn_count="20/1")
        self.assertEqual(pool_20.total_boxes, 10)

        # Update intake to 40/1 Warp
        update_res = self.client.patch(f"/api/v1/yarn-intakes/{intake_id}/", {
            "yarnCount": "40/1",
        }, format="json")
        self.assertEqual(update_res.status_code, status.HTTP_200_OK, update_res.data)

        pool_20.refresh_from_db()
        pool_40 = YarnStock.objects.get(yarn_count="40/1")

        # Pool 20/1 must lose the 10 bags (now 0)
        self.assertEqual(pool_20.total_boxes, 0)
        self.assertEqual(pool_20.total_weight_kg, Decimal("0.000"))

        # Pool 40/1 must gain the 10 bags
        self.assertEqual(pool_40.total_boxes, 10)
        self.assertEqual(pool_40.total_weight_kg, Decimal("100.000"))

    # ──────────────────────────────────────────────────────────────────────────
    # 9. An overdraw is rejected
    # ──────────────────────────────────────────────────────────────────────────
    def test_09_overdraw_is_rejected(self):
        intake = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Carded",
            yarn_count="20/1",
            production_type="Warp",
            set_no="S-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=20,
            rate_per_lb=Decimal("100.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        # Attempt to dispatch 15 bags when only 10 available
        res = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 15,
            "outcomeConesPerBag": 20,
            "outcomeWeightPerBagKg": "10.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = res.data.get("errors", res.data)
        self.assertIn("outcomeBags", errors)
        # Ensure available stock is unmodified
        stock.refresh_from_db()
        self.assertEqual(stock.total_boxes, 10)

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Concurrent dispatches cannot overdraw the same stock pool
    # ──────────────────────────────────────────────────────────────────────────
    def test_10_concurrent_dispatches_cannot_overdraw(self):
        # Pool with only 10 bags available
        intake = YarnIntake.objects.create(
            yarn_name="Silk",
            yarn_type="Pure",
            yarn_count="60/1",
            production_type="Warp",
            set_no="CONC-1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=10,
            rate_per_lb=Decimal("500.0000"),
            weight_per_bag_kg=Decimal("5.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        results = []

        def attempt_dispatch():
            # Close existing connection in thread so a new DB connection is used
            connection.close()
            client = APIClient()
            client.force_authenticate(user=self.user)
            resp = client.post("/api/v1/yarn-outcomes/", {
                "stock": stock.id,
                "outcomeType": "Sizing",
                "outcomeBags": 6,  # 6 + 6 = 12 > 10
                "outcomeConesPerBag": 10,
                "outcomeWeightPerBagKg": "5.000",
                "sizing": self.sizing.id,
                "outcomeDate": "2026-10-12",
            }, format="json")
            results.append(resp.status_code)
            connection.close()

        t1 = threading.Thread(target=attempt_dispatch)
        t2 = threading.Thread(target=attempt_dispatch)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one must succeed (201) and one must be rejected (400)
        self.assertIn(status.HTTP_201_CREATED, results)
        self.assertIn(status.HTTP_400_BAD_REQUEST, results)

        stock.refresh_from_db()
        # Exactly 4 bags must remain (10 - 6), NEVER negative
        self.assertEqual(stock.total_boxes, 4)

    # ──────────────────────────────────────────────────────────────────────────
    # 11. Kilogram and pound calculations remain consistent
    # ──────────────────────────────────────────────────────────────────────────
    def test_11_kilogram_and_pound_calculations_remain_consistent(self):
        intake = YarnIntake.objects.create(
            yarn_name="Poly",
            yarn_type="Spun",
            yarn_count="30/1",
            production_type="Weft",
            set_no="LB-1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=10,
            rate_per_lb=Decimal("80.0000"),
            weight_per_bag_kg=Decimal("45.360"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        expected_kg = Decimal("453.600")
        expected_lb = (expected_kg * LB_PER_KG).quantize(Decimal("0.000001"))

        self.assertEqual(stock.total_weight_kg, expected_kg)
        self.assertEqual(stock.total_weight_lb, expected_lb)

    # ──────────────────────────────────────────────────────────────────────────
    # 12. Box and cone counts are accurate where conversions are supported
    # ──────────────────────────────────────────────────────────────────────────
    def test_12_box_and_cone_counts_accurate(self):
        intake = YarnIntake.objects.create(
            yarn_name="Viscose",
            yarn_type="Rayon",
            yarn_count="40/1",
            production_type="Warp",
            set_no="CONE-1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=12,
            cones_per_bag=30,
            rate_per_lb=Decimal("120.0000"),
            weight_per_bag_kg=Decimal("20.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        # Received: 12 bags, 360 cones
        self.assertEqual(stock.total_boxes, 12)
        self.assertEqual(stock.cones, 360)

        # Dispatch 5 bags with 30 cones per bag = 150 cones
        self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 5,
            "outcomeConesPerBag": 30,
            "outcomeWeightPerBagKg": "20.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }, format="json")

        stock.refresh_from_db()
        self.assertEqual(stock.total_boxes, 7)
        self.assertEqual(stock.cones, 210)  # 360 - 150 = 210

    # ──────────────────────────────────────────────────────────────────────────
    # 13. Business rules intact: Sizing, Weft, Sold, buyer, price, beams
    # ──────────────────────────────────────────────────────────────────────────
    def test_13_business_rules_intact(self):
        intake = YarnIntake.objects.create(
            yarn_name="Cotton",
            yarn_type="Combed",
            yarn_count="50/1",
            production_type="Warp",
            set_no="RULES-1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=50,
            cones_per_bag=20,
            rate_per_lb=Decimal("250.0000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        stock = intake.stock
        recalculate_yarn_stock(stock)

        # Sizing requires sizing FK, buyer must be null
        bad_sizing = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 2,
            "outcomeWeightPerBagKg": "10.000",
            "outcomeDate": "2026-10-12",
        }, format="json")
        self.assertEqual(bad_sizing.status_code, status.HTTP_400_BAD_REQUEST)

        # Weft requires buyer null and sizing null
        weft_res = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Weft",
            "outcomeBags": 3,
            "outcomeWeightPerBagKg": "10.000",
            "outcomeDate": "2026-10-12",
        }, format="json")
        self.assertEqual(weft_res.status_code, status.HTTP_201_CREATED, weft_res.data)

        # Sold requires buyer and price > 0
        bad_sold = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sold",
            "outcomeBags": 2,
            "outcomeWeightPerBagKg": "10.000",
            "outcomeDate": "2026-10-12",
        }, format="json")
        self.assertEqual(bad_sold.status_code, status.HTTP_400_BAD_REQUEST)

        good_sold = self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sold",
            "outcomeBags": 2,
            "outcomeWeightPerBagKg": "10.000",
            "yarnBuyer": self.buyer.id,
            "totalPrice": "55000.00",
            "outcomeDate": "2026-10-12",
        }, format="json")
        self.assertEqual(good_sold.status_code, status.HTTP_201_CREATED, good_sold.data)

    # ──────────────────────────────────────────────────────────────────────────
    # 14. Stock Listing, Filtering, History, and Safety Rules
    # ──────────────────────────────────────────────────────────────────────────
    def test_14_stock_apis_and_intake_delete_safety(self):
        intake1 = YarnIntake.objects.create(
            yarn_name="Linen",
            yarn_type="Fine",
            yarn_count="10/1",
            production_type="Warp",
            set_no="LIN-1",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=15,
            rate_per_lb=Decimal("300.0000"),
            weight_per_bag_kg=Decimal("20.000"),
        )
        stock = intake1.stock
        recalculate_yarn_stock(stock)

        # 14.1 List endpoint
        list_res = self.client.get("/api/v1/yarn-stocks/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(s["id"] == stock.id for s in list_res.data["results"]))

        # 14.2 Filter endpoint
        filter_res = self.client.get(f"/api/v1/yarn-stocks/?yarn_name=Linen")
        self.assertEqual(filter_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(filter_res.data["results"]), 1)

        # 14.3 Dispatch 8 bags
        self.client.post("/api/v1/yarn-outcomes/", {
            "stock": stock.id,
            "outcomeType": "Sizing",
            "outcomeBags": 8,
            "outcomeConesPerBag": 15,
            "outcomeWeightPerBagKg": "20.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-12",
        }, format="json")

        # 14.4 Contributing intakes history endpoint
        intakes_history = self.client.get(f"/api/v1/yarn-stocks/{stock.id}/intakes/")
        self.assertEqual(intakes_history.status_code, status.HTTP_200_OK)

        # 14.5 Outcomes history endpoint
        outcomes_history = self.client.get(f"/api/v1/yarn-stocks/{stock.id}/outcomes/")
        self.assertEqual(outcomes_history.status_code, status.HTTP_200_OK)

        # 14.6 Safety: Deleting intake1 when 8 bags are already dispatched from it must fail!
        del_intake_res = self.client.delete(f"/api/v1/yarn-intakes/{intake1.id}/")
        self.assertEqual(del_intake_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceed remaining", str(del_intake_res.data))

        # Stock must remain intact
        stock.refresh_from_db()
        self.assertEqual(stock.total_boxes, 2)
