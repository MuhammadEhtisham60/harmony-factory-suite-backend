"""
Tests for YarnName, YarnType, and YarnCount models, viewsets, APIs,
and their ForeignKey integrations with YarnIntake and YarnStock.
"""

from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_intake.models import YarnIntake
from factory.yarn.yarn_stock.models import YarnStock


class YarnAttributeModelsAndAPITests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="yarn_attr_admin",
            email="yarn_attr_admin@example.com",
            password="adminpassword123",
        )
        self.client.force_authenticate(user=self.admin)

        self.supplier = Supplier.objects.create(
            supplier_name="Universal Mills Supplier",
            status="Active",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # YarnName CRUD & APIs
    # ──────────────────────────────────────────────────────────────────────────
    def test_yarn_name_crud_and_choices(self):
        # 1. Create
        create_res = self.client.post("/api/v1/yarn-names/", {
            "name": "Organic Cotton",
            "description": "Eco-friendly natural cotton",
            "status": "Active",
        }, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        name_id = create_res.data["data"]["id"]
        self.assertEqual(create_res.data["data"]["name"], "Organic Cotton")

        # 2. List & Filter
        list_res = self.client.get("/api/v1/yarn-names/?name=Organic")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(list_res.data["count"], 1)

        # 3. Retrieve
        get_res = self.client.get(f"/api/v1/yarn-names/{name_id}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["data"]["name"], "Organic Cotton")

        # 4. Choices endpoint
        choices_res = self.client.get("/api/v1/yarn-names/choices/")
        self.assertEqual(choices_res.status_code, status.HTTP_200_OK)
        ids = [c["id"] for c in choices_res.data["data"]]
        self.assertIn(name_id, ids)

        # 5. Update
        update_res = self.client.patch(f"/api/v1/yarn-names/{name_id}/", {
            "description": "Updated remarks",
        }, format="json")
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data["data"]["description"], "Updated remarks")

        # 6. Delete
        delete_res = self.client.delete(f"/api/v1/yarn-names/{name_id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_200_OK)
        self.assertFalse(YarnName.objects.filter(id=name_id).exists())

    # ──────────────────────────────────────────────────────────────────────────
    # YarnType CRUD & APIs
    # ──────────────────────────────────────────────────────────────────────────
    def test_yarn_type_crud_and_choices(self):
        # 1. Create
        create_res = self.client.post("/api/v1/yarn-types/", {
            "name": "Combed Compact",
            "description": "High tenacity compact spun",
            "status": "Active",
        }, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        type_id = create_res.data["data"]["id"]
        self.assertEqual(create_res.data["data"]["name"], "Combed Compact")

        # 2. Choices endpoint
        choices_res = self.client.get("/api/v1/yarn-types/choices/")
        self.assertEqual(choices_res.status_code, status.HTTP_200_OK)
        ids = [c["id"] for c in choices_res.data["data"]]
        self.assertIn(type_id, ids)

        # 3. Update & Delete
        self.client.patch(f"/api/v1/yarn-types/{type_id}/", {"status": "Inactive"}, format="json")
        inactive_choices = self.client.get("/api/v1/yarn-types/choices/")
        self.assertNotIn(type_id, [c["id"] for c in inactive_choices.data["data"]])

        del_res = self.client.delete(f"/api/v1/yarn-types/{type_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

    # ──────────────────────────────────────────────────────────────────────────
    # YarnCount CRUD & APIs
    # ──────────────────────────────────────────────────────────────────────────
    def test_yarn_count_crud_and_choices(self):
        # 1. Create
        create_res = self.client.post("/api/v1/yarn-counts/", {
            "name": "60s / 1 Combed",
            "description": "Fine yarn count",
            "status": "Active",
        }, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        count_id = create_res.data["data"]["id"]

        # 2. Choices endpoint
        choices_res = self.client.get("/api/v1/yarn-counts/choices/")
        self.assertEqual(choices_res.status_code, status.HTTP_200_OK)
        ids = [c["id"] for c in choices_res.data["data"]]
        self.assertIn(count_id, ids)

        # 3. Delete
        del_res = self.client.delete(f"/api/v1/yarn-counts/{count_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

    # ──────────────────────────────────────────────────────────────────────────
    # ForeignKey integration in YarnIntake and YarnStock
    # ──────────────────────────────────────────────────────────────────────────
    def test_yarn_intake_creation_with_foreign_keys_by_id(self):
        """Test creating an intake using explicit foreign key IDs."""
        y_name = YarnName.objects.create(name="Supima Cotton")
        y_type = YarnType.objects.create(name="Ring Spun Extra")
        y_count = YarnCount.objects.create(name="80s / 2")

        post_res = self.client.post("/api/v1/yarn-intakes/", {
            "yarnNameId": y_name.id,
            "yarnTypeId": y_type.id,
            "yarnCountId": y_count.id,
            "productionType": "Warp",
            "intakeDate": "2026-10-13",
            "supplier": self.supplier.id,
            "bags": 15,
            "conesPerBag": 24,
            "ratePerLb": "250.0000",
            "weightPerBagKg": "45.000",
        }, format="json")

        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED, post_res.data)
        data = post_res.data["data"]

        # Check response fields
        self.assertEqual(data["yarnName"], "Supima Cotton")
        self.assertEqual(data["yarnType"], "Ring Spun Extra")
        self.assertEqual(data["yarnCount"], "80s / 2")
        self.assertEqual(data["yarnNameId"], y_name.id)
        self.assertEqual(data["yarnTypeId"], y_type.id)
        self.assertEqual(data["yarnCountId"], y_count.id)
        self.assertEqual(data["yarnNameDetail"]["name"], "Supima Cotton")

        # Verify DB YarnIntake record links to the exact FK objects
        intake = YarnIntake.objects.get(id=data["id"])
        self.assertEqual(intake.yarn_name, y_name)
        self.assertEqual(intake.yarn_type, y_type)
        self.assertEqual(intake.yarn_count, y_count)

        # Verify YarnStock pool links to the exact FK objects
        stock = intake.stock
        self.assertIsNotNone(stock)
        self.assertEqual(stock.yarn_name, y_name)
        self.assertEqual(stock.yarn_type, y_type)
        self.assertEqual(stock.yarn_count, y_count)
        self.assertEqual(stock.total_boxes, 15)

    def test_yarn_intake_creation_with_string_auto_resolution(self):
        """Test creating an intake using string names auto-creates foreign keys."""
        post_res = self.client.post("/api/v1/yarn-intakes/", {
            "yarnName": "Bamboo Blend",
            "yarnType": "Air Jet Spun",
            "yarnCount": "50s / 1",
            "productionType": "Weft",
            "intakeDate": "2026-10-13",
            "supplier": self.supplier.id,
            "bags": 5,
            "conesPerBag": 12,
            "ratePerLb": "90.0000",
            "weightPerBagKg": "25.000",
        }, format="json")

        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED, post_res.data)

        # Verify models were auto-created
        self.assertTrue(YarnName.objects.filter(name="Bamboo Blend").exists())
        self.assertTrue(YarnType.objects.filter(name="Air Jet Spun").exists())
        self.assertTrue(YarnCount.objects.filter(name="50s / 1").exists())

        y_name = YarnName.objects.get(name="Bamboo Blend")
        y_type = YarnType.objects.get(name="Air Jet Spun")
        y_count = YarnCount.objects.get(name="50s / 1")

        intake = YarnIntake.objects.get(id=post_res.data["data"]["id"])
        self.assertEqual(intake.yarn_name, y_name)
        self.assertEqual(intake.yarn_type, y_type)
        self.assertEqual(intake.yarn_count, y_count)

    def test_stock_list_serializer_includes_fk_details(self):
        """Verify YarnStock list/detail endpoints output yarn details and IDs."""
        y_name = YarnName.objects.create(name="Tencel Luxe")
        y_type = YarnType.objects.create(name="Micro Modal")
        y_count = YarnCount.objects.create(name="100s / 2")

        intake = YarnIntake.objects.create(
            yarn_name=y_name,
            yarn_type=y_type,
            yarn_count=y_count,
            production_type="Warp",
            intake_date="2026-10-13",
            supplier=self.supplier,
            bags=10,
            cones_per_bag=20,
            weight_per_bag_kg=Decimal("20.000"),
            rate_per_lb=Decimal("150.0000"),
        )

        stock_res = self.client.get(f"/api/v1/yarn-stocks/{intake.stock.id}/")
        self.assertEqual(stock_res.status_code, status.HTTP_200_OK)
        stock_data = stock_res.data["data"]

        self.assertEqual(stock_data["yarnName"], "Tencel Luxe")
        self.assertEqual(stock_data["yarnType"], "Micro Modal")
        self.assertEqual(stock_data["yarnCount"], "100s / 2")
        self.assertEqual(stock_data["yarnNameId"], y_name.id)
        self.assertEqual(stock_data["yarnTypeId"], y_type.id)
        self.assertEqual(stock_data["yarnCountId"], y_count.id)
        self.assertEqual(stock_data["yarnNameDetail"]["name"], "Tencel Luxe")
        self.assertEqual(stock_data["yarnTypeDetail"]["name"], "Micro Modal")
        self.assertEqual(stock_data["yarnCountDetail"]["name"], "100s / 2")
