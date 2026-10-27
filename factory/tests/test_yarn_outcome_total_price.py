from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from factory.purchase.supplier.models import Supplier
from factory.yarn.sizing.models import Sizing
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome, YarnOutcomeItem, LB_PER_KG
from factory.yarn.yarn_stock.models import YarnStock

User = get_user_model()


class YarnOutcomeTotalPriceTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_outcome_price_test",
            email="outcome_price_test@example.com",
            password="Password@123",
            status="Active"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            supplier_name="Super Mills Ltd",
            supplier_code="SML-001",
            status="Active"
        )

        self.sizing = Sizing.objects.create(
            sizing_name="Star Sizing Mill",
            status="Active"
        )

        self.yarn_name = YarnName.objects.create(name="Cotton")
        self.yarn_type = YarnType.objects.create(name="Carded")
        self.yarn_count = YarnCount.objects.create(name="30/1")

    def test_sizing_outcome_saves_dispatched_yarn_price(self):
        """
        When dispatching yarn to Sizing, YarnOutcome.total_price must save
        the exact financial value of the dispatched yarn (e.g. Rs 30,000).
        """
        # Intake: 20 bags @ 150 PKR/lb. Each bag = 10 kg (~22.046226 lb)
        # 10 bags dispatched = 100 kg = 220.462262 lb.
        # At 150 PKR/lb, value = 220.462262 * 150 = 33,069.339328 PKR
        intake = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            set_no="INTAKE-30K",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=20,
            cones_per_bag=12,
            rate_per_lb=Decimal("150.000000"),
            weight_per_bag_kg=Decimal("10.000"),
        )

        # Dispatch 10 bags via API
        payload = {
            "outcomeType": "Sizing",
            "outcomeBags": 10,
            "outcomeConesPerBag": 12,
            "outcomeWeightPerBagKg": "10.000",
            "sizing": self.sizing.id,
            "outcomeDate": "2026-10-23",
            "intakes": [
                {
                    "yarnIntake": intake.id,
                    "bags": 10,
                    "conesPerBag": 12,
                    "weightPerBagKg": "10.000",
                }
            ]
        }
        res = self.client.post("/api/v1/yarn-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        outcome_id = res.data.get("id") or (res.data.get("data") and res.data["data"].get("id"))
        outcome = YarnOutcome.objects.get(pk=outcome_id)

        # Dispatched weight in lb: 10 * 10 * LB_PER_KG
        expected_weight_lb = Decimal("100.000000") * LB_PER_KG
        expected_price = (expected_weight_lb * Decimal("150.000000")).quantize(Decimal("0.000001"))

        # Verify total_price saved in YarnOutcome is non-zero and matches the dispatched yarn value!
        self.assertGreater(outcome.total_price, Decimal("0.000000"))
        self.assertEqual(outcome.total_price, expected_price)

    def test_weft_outcome_saves_dispatched_yarn_price(self):
        """
        When dispatching yarn to Weft, YarnOutcome.total_price must save
        the exact financial value of the dispatched yarn.
        """
        intake = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            set_no="WEFT-INTAKE",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=10,
            rate_per_lb=Decimal("100.000000"),
            weight_per_bag_kg=Decimal("15.000"),
        )

        payload = {
            "outcomeType": "Weft",
            "outcomeBags": 5,
            "outcomeConesPerBag": 10,
            "outcomeWeightPerBagKg": "15.000",
            "outcomeDate": "2026-10-23",
            "intakes": [
                {
                    "yarnIntake": intake.id,
                    "bags": 5,
                    "conesPerBag": 10,
                    "weightPerBagKg": "15.000",
                }
            ]
        }
        res = self.client.post("/api/v1/yarn-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        outcome_id = res.data.get("id") or (res.data.get("data") and res.data["data"].get("id"))
        outcome = YarnOutcome.objects.get(pk=outcome_id)

        # 5 bags * 15 kg = 75 kg * LB_PER_KG * 100 Rs/lb
        expected_weight_lb = (Decimal("75.000000") * LB_PER_KG).quantize(Decimal("0.000001"))
        expected_price = (expected_weight_lb * Decimal("100.000000")).quantize(Decimal("0.000001"))
        self.assertEqual(outcome.total_price, expected_price)

    def test_direct_yarn_outcome_save_calculates_total_price(self):
        """
        Creating a YarnOutcome directly in Python with initial intake sets total_price.
        """
        intake = YarnIntake.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            set_no="DIRECT-01",
            intake_date=timezone.now().date(),
            supplier=self.supplier,
            bags=10,
            cones_per_bag=10,
            rate_per_lb=Decimal("200.000000"),
            weight_per_bag_kg=Decimal("10.000"),
        )

        outcome = YarnOutcome.objects.create(
            yarn_intake=intake,
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing=self.sizing,
            outcome_bags=3,
            outcome_cones_per_bag=10,
            outcome_weight_per_bag_kg=Decimal("10.000"),
            outcome_date=timezone.now().date(),
        )

        expected_weight_lb = (Decimal("30.000000") * LB_PER_KG).quantize(Decimal("0.000001"))
        expected_price = (expected_weight_lb * Decimal("200.000000")).quantize(Decimal("0.000001"))
        self.assertEqual(outcome.total_price, expected_price)
