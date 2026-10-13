"""
Tests for YarnIntake set_no auto-generation (BATCH-01, BATCH-02, ...).
"""

from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_intake.models import YarnIntake


class YarnIntakeSetNoAutoGenerateTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="intake_admin",
            email="intake_admin@example.com",
            password="adminpassword123",
        )
        self.client.force_authenticate(user=self.admin)

        self.supplier = Supplier.objects.create(
            supplier_name="Premier Yarn Supplier",
            status="Active",
        )

    def test_model_auto_generate_first_batch(self):
        """When set_no is omitted or blank, the first batch gets BATCH-01."""
        intake1 = YarnIntake.objects.create(
            yarn_name="Cotton 30/1",
            yarn_type="Carded",
            yarn_count="30/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=20,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("15000"),
        )
        self.assertEqual(intake1.set_no, "BATCH-01")

        intake2 = YarnIntake.objects.create(
            yarn_name="Cotton 30/1",
            yarn_type="Carded",
            yarn_count="30/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=10,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("15000"),
        )
        self.assertEqual(intake2.set_no, "BATCH-02")

        intake3 = YarnIntake.objects.create(
            yarn_name="Cotton 40/1",
            yarn_type="Combed",
            yarn_count="40/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=15,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("18000"),
            set_no="",  # Explicit empty string
        )
        self.assertEqual(intake3.set_no, "BATCH-03")

    def test_manual_set_no_preserved(self):
        """When manual set_no is provided, it is preserved, and next auto batch increments from max BATCH-."""
        custom_intake = YarnIntake.objects.create(
            yarn_name="Cotton 20/1",
            yarn_type="Carded",
            yarn_count="20/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=5,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("12000"),
            set_no="CUSTOM-LOT-88",
        )
        self.assertEqual(custom_intake.set_no, "CUSTOM-LOT-88")

        # Now create BATCH-05 manually
        manual_batch5 = YarnIntake.objects.create(
            yarn_name="Cotton 20/1",
            yarn_type="Carded",
            yarn_count="20/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=5,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("12000"),
            set_no="BATCH-05",
        )
        self.assertEqual(manual_batch5.set_no, "BATCH-05")

        # Next auto-generated intake should be BATCH-06
        next_intake = YarnIntake.objects.create(
            yarn_name="Cotton 20/1",
            yarn_type="Carded",
            yarn_count="20/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=5,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("12000"),
        )
        self.assertEqual(next_intake.set_no, "BATCH-06")

    def test_api_create_without_set_no(self):
        """POST /api/v1/yarn-intakes/ without setNo successfully creates with auto-generated BATCH-xx."""
        payload = {
            "yarnName": "Cotton 20/1",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "supplier": self.supplier.id,
            "intakeDate": "2026-10-13",
            "bags": 30,
            "conesPerBag": 24,
            "ratePerBag": "16000.00",
            "weightPerBagKg": "45.360",
        }
        response = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        data = response.data.get("data", {})
        self.assertTrue(data.get("setNo", "").startswith("BATCH-"))
        created_set_no = data["setNo"]

        # Second creation via API also increments
        payload["yarnName"] = "Cotton 40/1"
        response2 = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED, response2.data)
        data2 = response2.data.get("data", {})
        self.assertNotEqual(data2["setNo"], created_set_no)
        self.assertTrue(data2["setNo"].startswith("BATCH-"))

    def test_api_create_with_custom_set_no(self):
        """POST /api/v1/yarn-intakes/ with explicit setNo preserves user value."""
        payload = {
            "yarnName": "Cotton 20/1",
            "yarnType": "Carded",
            "yarnCount": "20/1",
            "setNo": "LOT-SPECIAL-99",
            "supplier": self.supplier.id,
            "intakeDate": "2026-10-13",
            "bags": 10,
            "conesPerBag": 24,
            "ratePerBag": "15000.00",
            "weightPerBagKg": "45.360",
        }
        response = self.client.post("/api/v1/yarn-intakes/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["data"]["setNo"], "LOT-SPECIAL-99")

    def test_filter_by_set_no(self):
        """GET /api/v1/yarn-intakes/?set_no=BATCH- filters by set_no."""
        intake = YarnIntake.objects.create(
            yarn_name="Cotton 30/1",
            yarn_type="Carded",
            yarn_count="30/1",
            supplier=self.supplier,
            intake_date="2026-10-13",
            bags=20,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("15000"),
        )
        res = self.client.get("/api/v1/yarn-intakes/", {"set_no": intake.set_no})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["setNo"] == intake.set_no for item in res.data["results"]))
