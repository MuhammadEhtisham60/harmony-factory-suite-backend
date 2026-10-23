from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_intake.models import YarnIntake
from factory.yarn.yarn_stock.models import YarnStock
from factory.yarn.yarn_stock.services import (
    recalculate_yarn_stock,
    reconcile_intake_stock_pools,
    get_or_create_yarn_stock,
)

User = get_user_model()


class ConversionYarnStockTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_conv_test",
            email="conv_test@example.com",
            password="Password@123",
            status="Active"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            supplier_name="Global Textiles Ltd",
            supplier_code="GTL-001",
            status="Active"
        )

        self.yarn_name = YarnName.objects.create(name="DTY")
        self.yarn_type = YarnType.objects.create(name="polyster")
        self.yarn_count = YarnCount.objects.create(name="150/144")

    def test_conversion_and_self_create_separate_stock_pools(self):
        """
        Conversion intake and Self intake for the same yarn specifications
        must exist in separate YarnStock pools.
        """
        # 1. Create Conversion intake (rate = 0, productionType = 'Conversion')
        conv_payload = {
            "yarnName": "DTY",
            "yarnType": "polyster",
            "yarnCount": "150/144",
            "productionType": "Conversion",
            "setNo": "CONV-01",
            "intakeDate": "2026-10-23",
            "supplier": self.supplier.id,
            "bags": 20,
            "conesPerBag": 10,
            "ratePerLb": "0.000000",
            "weightPerBagKg": "10.000",
        }
        res_conv = self.client.post("/api/v1/yarn-intakes/", conv_payload, format="json")
        self.assertEqual(res_conv.status_code, status.HTTP_201_CREATED, res_conv.data)

        # 2. Create Self intake for same specs (rate = 120, productionType = 'Self')
        self_payload = {
            "yarnName": "DTY",
            "yarnType": "polyster",
            "yarnCount": "150/144",
            "productionType": "Self",
            "setNo": "SELF-01",
            "intakeDate": "2026-10-23",
            "supplier": self.supplier.id,
            "bags": 30,
            "conesPerBag": 10,
            "ratePerLb": "120.000000",
            "weightPerBagKg": "10.000",
        }
        res_self = self.client.post("/api/v1/yarn-intakes/", self_payload, format="json")
        self.assertEqual(res_self.status_code, status.HTTP_201_CREATED, res_self.data)

        # Exactly 2 stock pools must exist: one Conversion and one Self
        self.assertEqual(YarnStock.objects.count(), 2)

        conv_stock = YarnStock.objects.get(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Conversion"
        )
        self_stock = YarnStock.objects.get(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self"
        )

        self.assertEqual(conv_stock.total_boxes, 20)
        self.assertEqual(conv_stock.total_price, Decimal("0.000000"))
        self.assertEqual(conv_stock.remaining_total_price, Decimal("0.000000"))

        self.assertEqual(self_stock.total_boxes, 30)
        self.assertGreater(self_stock.remaining_total_price, Decimal("0.000000"))

    def test_infer_conversion_when_rate_is_zero(self):
        """
        When productionType is omitted, rate=0 should automatically infer Conversion pool.
        """
        payload = {
            "yarnName": "DTY",
            "yarnType": "polyster",
            "yarnCount": "150/144",
            "setNo": "ZERO-01",
            "intakeDate": "2026-10-23",
            "supplier": self.supplier.id,
            "bags": 15,
            "conesPerBag": 10,
            "ratePerLb": "0.000000",
            "weightPerBagKg": "10.000",
        }
        res = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        intake = YarnIntake.objects.get(set_no="ZERO-01")
        self.assertEqual(intake.production_type, "Conversion")
        self.assertEqual(intake.stock.production_type, "Conversion")

    def test_reconcile_intake_stock_pools(self):
        """
        reconcile_intake_stock_pools should re-sort any unassigned or misassigned intakes
        into distinct Conversion vs Self pools.
        """
        # Create an intake directly in DB with empty production_type and rate=0
        intake_conv = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="",
            set_no="REC-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=6,
            rate_per_lb=Decimal("0.000000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        # Create a second intake directly in DB with rate > 0
        intake_self = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="",
            set_no="REC-02",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=12,
            cones_per_bag=6,
            rate_per_lb=Decimal("150.000000"),
            weight_per_bag_kg=Decimal("10.000"),
        )

        reconcile_intake_stock_pools()

        intake_conv.refresh_from_db()
        intake_self.refresh_from_db()

        self.assertEqual(intake_conv.production_type, "Conversion")
        self.assertEqual(intake_self.production_type, "Self")
        self.assertNotEqual(intake_conv.stock_id, intake_self.stock_id)
        self.assertEqual(intake_conv.stock.production_type, "Conversion")
        self.assertEqual(intake_self.stock.production_type, "Self")

    def test_update_intake_moves_between_conversion_and_self(self):
        """
        Updating an intake's productionType moves it from one pool to the other,
        updating counts and valuations on both pools accordingly.
        """
        intake = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Conversion",
            set_no="MOVE-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=6,
            rate_per_lb=Decimal("0.000000"),
            weight_per_bag_kg=Decimal("10.000"),
        )
        conv_stock = intake.stock
        self.assertEqual(conv_stock.production_type, "Conversion")
        self.assertEqual(conv_stock.total_boxes, 10)

        # Update intake to Self with a positive rate
        update_payload = {
            "yarnName": "DTY",
            "yarnType": "polyster",
            "yarnCount": "150/144",
            "productionType": "Self",
            "ratePerLb": "120.000000",
            "bags": 10,
            "conesPerBag": 6,
            "weightPerBagKg": "10.000",
            "supplier": self.supplier.id,
            "intakeDate": "2026-10-23",
            "setNo": "MOVE-01",
        }
        res = self.client.put(f"/api/v1/yarn-intakes/{intake.id}/", update_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        intake.refresh_from_db()
        self.assertEqual(intake.production_type, "Self")
        self.assertEqual(intake.stock.production_type, "Self")
        self.assertNotEqual(intake.stock_id, conv_stock.id)
        self.assertEqual(intake.stock.total_boxes, 10)
        self.assertGreater(intake.stock.remaining_total_price, Decimal("0.000000"))

        conv_stock.refresh_from_db()
        self.assertEqual(conv_stock.total_boxes, 0)

