"""
Tests for B-Grade Yarn model, serializers, and ModelViewSet.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.b_grade_yarn.models import BGradeYarn, LB_PER_KG

User = get_user_model()


class BGradeYarnTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.yarn_name = YarnName.objects.create(name="Cotton OE")
        self.yarn_type = YarnType.objects.create(name="100% Combed Cotton")
        self.yarn_count = YarnCount.objects.create(name="30s / 1")

    def test_model_creation_and_weight_sync(self):
        """Test BGradeYarn model creates properly and auto-syncs weight_lb from weight_kg."""
        item = BGradeYarn.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            cones=50,
            weight_kg=Decimal("25.000000"),
            lot_number="LOT-B-001",
        )
        self.assertEqual(item.cones, 50)
        expected_lb = (Decimal("25.000000") * LB_PER_KG).quantize(Decimal("0.000001"))
        self.assertEqual(item.weight_lb, expected_lb)

    def test_no_boxes_and_no_price_fields_in_model(self):
        """Ensure boxes/bags and price fields do NOT exist on the model."""
        fields = [f.name for f in BGradeYarn._meta.get_fields()]
        for prohibited in [
            "boxes", "bags", "total_boxes", "remaining_bags",
            "price", "total_price", "rate_per_lb", "remaining_total_price"
        ]:
            self.assertNotIn(prohibited, fields, f"Prohibited field '{prohibited}' should not exist in BGradeYarn.")

    def test_crud_endpoints(self):
        """Test CRUD operations via ModelViewSet."""
        # Create
        create_payload = {
            "yarnName": "Cotton OE",
            "yarnType": "100% Combed Cotton",
            "yarnCount": "30s / 1",
            "productionType": "Self",
            "cones": 80,
            "weightKg": "40.0000",
            "lotNumber": "LOT-TEST-01",
            "remarks": "Minor slub defects",
        }
        res = self.client.post("/api/v1/b-grade-yarn/", create_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        item_id = res.data["data"]["id"]

        # List
        res_list = self.client.get("/api/v1/b-grade-yarn/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data["count"], 1)

        # Retrieve
        res_get = self.client.get(f"/api/v1/b-grade-yarn/{item_id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["data"]["cones"], 80)
        self.assertEqual(res_get.data["data"]["lotNumber"], "LOT-TEST-01")

        # Update
        update_payload = {"cones": 95, "remarks": "Updated remark"}
        res_update = self.client.patch(f"/api/v1/b-grade-yarn/{item_id}/", update_payload, format="json")
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(res_update.data["data"]["cones"], 95)

        # Delete
        res_delete = self.client.delete(f"/api/v1/b-grade-yarn/{item_id}/")
        self.assertEqual(res_delete.status_code, status.HTTP_200_OK)
        self.assertEqual(BGradeYarn.objects.count(), 0)

    def test_quality_wise_aggregated_endpoint(self):
        """Test quality-wise action groups batches by quality like yarn-stock."""
        # Batch 1 for Quality A
        BGradeYarn.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            cones=50,
            weight_kg=Decimal("20.000000"),
            lot_number="LOT-A1",
        )
        # Batch 2 for Quality A
        BGradeYarn.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type="Self",
            cones=70,
            weight_kg=Decimal("30.000000"),
            lot_number="LOT-A2",
        )
        # Batch 3 for Quality B (Different count)
        count2 = YarnCount.objects.create(name="40s / 1")
        BGradeYarn.objects.create(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=count2,
            production_type="Self",
            cones=100,
            weight_kg=Decimal("45.000000"),
            lot_number="LOT-B1",
        )

        res = self.client.get("/api/v1/b-grade-yarn/quality-wise/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data["results"]
        self.assertEqual(len(results), 2)  # 2 distinct qualities

        # Quality A verification: 50 + 70 = 120 cones, 20 + 30 = 50 kg
        qual_a = next(r for r in results if r["yarnCount"] == "30s / 1")
        self.assertEqual(qual_a["totalCones"], 120)
        self.assertEqual(Decimal(qual_a["totalWeightKg"]), Decimal("50.0000"))
        self.assertEqual(qual_a["entriesCount"], 2)
        self.assertIn("LOT-A1", qual_a["lotNumbers"])
        self.assertIn("LOT-A2", qual_a["lotNumbers"])

        # Quality B verification: 100 cones, 45 kg
        qual_b = next(r for r in results if r["yarnCount"] == "40s / 1")
        self.assertEqual(qual_b["totalCones"], 100)
        self.assertEqual(Decimal(qual_b["totalWeightKg"]), Decimal("45.0000"))
        self.assertEqual(qual_b["entriesCount"], 1)

        # Verify summary stats
        summary = res.data["summary"]
        self.assertEqual(summary["totalQualities"], 2)
        self.assertEqual(summary["totalCones"], 220)
        self.assertEqual(summary["totalWeightKg"], Decimal("95.0000"))
