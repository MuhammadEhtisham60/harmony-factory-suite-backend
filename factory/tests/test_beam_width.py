"""
Tests for Beam width field, CRUD operations, filters, ordering, and integrations.
"""

from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.beam.models import Beam, BeamLoading
from factory.loom.models import Loom
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.yarn.sizing.serializers import BeamMinSerializer
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome


class BeamWidthTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="beam_admin",
            email="beam_admin@example.com",
            password="adminpassword123",
        )
        self.client.force_authenticate(user=self.admin)

        self.beam1 = Beam.objects.create(
            beam_number="BM-W101",
            beam_name="Narrow Beam",
            yarn_count="30/1",
            warp_count=2000,
            total_ends=2000,
            length=Decimal("1500.00"),
            width=Decimal("58.50"),
            weight=Decimal("200.00"),
            status=Beam.StatusChoices.AVAILABLE,
        )

        self.beam2 = Beam.objects.create(
            beam_number="BM-W102",
            beam_name="Standard Beam",
            yarn_count="30/1",
            warp_count=2400,
            total_ends=2400,
            length=Decimal("1800.00"),
            width=Decimal("68.00"),
            weight=Decimal("250.00"),
            status=Beam.StatusChoices.AVAILABLE,
        )

        self.beam3 = Beam.objects.create(
            beam_number="BM-W103",
            beam_name="Wide Beam",
            yarn_count="40/1",
            warp_count=3200,
            total_ends=3200,
            length=Decimal("2200.00"),
            width=Decimal("120.00"),
            weight=Decimal("380.00"),
            status=Beam.StatusChoices.AVAILABLE,
        )

        self.beam_null_width = Beam.objects.create(
            beam_number="BM-W104",
            beam_name="No Width Beam",
            yarn_count="20/1",
            status=Beam.StatusChoices.AVAILABLE,
        )

    def test_model_width_field(self):
        """Test model creation and persistence of width."""
        beam = Beam.objects.get(beam_number="BM-W101")
        self.assertEqual(beam.width, Decimal("58.50"))

        beam_null = Beam.objects.get(beam_number="BM-W104")
        self.assertIsNone(beam_null.width)

    def test_create_beam_with_width_api(self):
        """Test creating a Beam with width via POST endpoint."""
        payload = {
            "beamNumber": "BM-W105",
            "beamName": "Created Width Beam",
            "yarnCount": "40/1",
            "warpCount": 2800,
            "totalEnds": 2800,
            "length": "2000.00",
            "width": "72.50",
            "weight": "310.00",
            "status": "Available",
            "notes": "Testing width field creation",
        }
        response = self.client.post("/api/v1/factory/beams/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data.get("data", {})
        self.assertEqual(data["beamNumber"], "BM-W105")
        self.assertEqual(Decimal(str(data["width"])), Decimal("72.50"))

        # Verify DB record
        db_beam = Beam.objects.get(beam_number="BM-W105")
        self.assertEqual(db_beam.width, Decimal("72.50"))

    def test_update_beam_width_api(self):
        """Test partial and full update of width via PATCH/PUT."""
        # PATCH
        response = self.client.patch(
            f"/api/v1/factory/beams/{self.beam1.id}/",
            {"width": "60.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(response.data["data"]["width"])), Decimal("60.00"))

        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.width, Decimal("60.00"))

    def test_filter_beams_by_width(self):
        """Test filtering beams by width, min_width, and max_width."""
        # Exact width filter
        response = self.client.get("/api/v1/factory/beams/", {"width": "68.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["beamNumber"], "BM-W102")

        # min_width filter
        response = self.client.get("/api/v1/factory/beams/", {"min_width": "68.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        numbers = [r["beamNumber"] for r in response.data["results"]]
        self.assertIn("BM-W102", numbers)
        self.assertIn("BM-W103", numbers)
        self.assertNotIn("BM-W101", numbers)

        # max_width filter
        response = self.client.get("/api/v1/factory/beams/", {"max_width": "65.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        numbers = [r["beamNumber"] for r in response.data["results"]]
        self.assertIn("BM-W101", numbers)
        self.assertNotIn("BM-W102", numbers)
        self.assertNotIn("BM-W103", numbers)

    def test_ordering_by_width(self):
        """Test ordering beams by width ascending and descending."""
        response_asc = self.client.get("/api/v1/factory/beams/", {"ordering": "width", "min_width": "0"})
        self.assertEqual(response_asc.status_code, status.HTTP_200_OK)
        results_asc = response_asc.data["results"]
        self.assertEqual(results_asc[0]["beamNumber"], "BM-W101")
        self.assertEqual(results_asc[1]["beamNumber"], "BM-W102")
        self.assertEqual(results_asc[2]["beamNumber"], "BM-W103")

        response_desc = self.client.get("/api/v1/factory/beams/", {"ordering": "-width", "min_width": "0"})
        self.assertEqual(response_desc.status_code, status.HTTP_200_OK)
        results = response_desc.data["results"]
        # Top result should be BM-W103 (120.00)
        self.assertEqual(results[0]["beamNumber"], "BM-W103")
        self.assertEqual(results[1]["beamNumber"], "BM-W102")
        self.assertEqual(results[2]["beamNumber"], "BM-W101")

    def test_beam_min_serializer_includes_width(self):
        """Test BeamMinSerializer outputs width."""
        serializer = BeamMinSerializer(self.beam1)
        self.assertIn("width", serializer.data)
        self.assertEqual(Decimal(str(serializer.data["width"])), Decimal("58.50"))

    def test_beam_loading_inherits_beam_width(self):
        """Test load_beam_onto_loom uses beam.width when loading width is omitted."""
        from factory.beam.services import load_beam_onto_loom
        from factory.purchase.supplier.models import Supplier

        # Setup Loom, Supplier and SizingOutcome
        supplier = Supplier.objects.create(supplier_name="Supplier Width Test", status="Active")
        loom = Loom.objects.create(
            loom_code="L-W01",
            loom_name="Loom W01",
            status=Loom.StatusChoices.ACTIVE,
        )
        sizing = Sizing.objects.create(sizing_name="Sizing Unit W")
        intake = YarnIntake.objects.create(
            yarn_name="Cotton Warp 30/1",
            yarn_type="Warp",
            yarn_count="30/1",
            supplier=supplier,
            bags=10,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_lb=Decimal("150"),
            intake_date="2026-10-01",
        )
        yo = YarnOutcome.objects.create(
            yarn_intake=intake,
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing=sizing,
            outcome_bags=10,
            outcome_date="2026-10-02",
        )
        so = SizingOutcome.objects.create(
            yarn_outcome=yo,
            set_no="SET-W01",
            sizing_name="Sizing Unit W",
            outcome_date="2026-10-02",
        )

        # Transition beam to LOADED as expected by load_beam_onto_loom
        self.beam2.status = Beam.StatusChoices.LOADED
        self.beam2.save()

        # Load without passing width
        loading = load_beam_onto_loom(
            sizing_outcome=so,
            beam_or_id=self.beam2,
            loom_or_id=loom,
            user=self.admin,
        )
        self.assertEqual(loading.width, Decimal("68.00"))
