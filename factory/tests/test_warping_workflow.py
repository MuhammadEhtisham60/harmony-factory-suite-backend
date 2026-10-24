"""
Tests for Warping Master and Processing Mill Workflow.
Tests:
- Warping CRUD endpoints, choices endpoint, outcomes action
- Warping validation on YarnOutcome (requires warping FK, rejects without it, cleans other fields)
- Beam dispatch to Warping sets beam.status == Beam.StatusChoices.WARPING
- YarnOutcome status transitions (In Warping -> Partially Received -> Received)
- Deleting Warping YarnOutcome reverts beams to Available
- SizingOutcome filtering by warping and outcome_type
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.purchase.supplier.models import Supplier
from factory.beam.models import Beam
from factory.yarn.warping.models import Warping
from factory.yarn.sizing.models import SizingOutcome
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome


class WarpingWorkflowTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",
        )
        self.client.force_authenticate(user=self.admin)

        self.warping = Warping.objects.create(
            warping_name="Fast Warping Mills",
            contact_person="Ahmed",
            phone_no="03001234567",
            status=Warping.StatusChoices.ACTIVE,
        )

        self.supplier = Supplier.objects.create(
            supplier_name="Test Yarn Supplier",
            status="Active",
        )
        self.intake = YarnIntake.objects.create(
            yarn_name="Cotton 40s",
            yarn_type="Warp",
            yarn_count="40/1",
            supplier=self.supplier,
            bags=100,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_lb=Decimal("250.00"),
            intake_date=timezone.now().date(),
        )

        self.beam1 = Beam.objects.create(
            beam_name="B-101",
            beam_number="BM-101",
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam2 = Beam.objects.create(
            beam_name="B-102",
            beam_number="BM-102",
            status=Beam.StatusChoices.AVAILABLE,
        )

    def test_warping_crud_and_choices(self):
        # List
        res = self.client.get("/api/v1/warpings/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Choices
        res = self.client.get("/api/v1/warpings/choices/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(c["label"] == "Fast Warping Mills" for c in res.data["data"]))

        # Create
        res = self.client.post("/api/v1/warpings/", {
            "warpingName": "Speed Warping",
            "contactPerson": "Kamran",
            "phoneNo": "03111111111",
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        new_id = res.data["data"]["id"]

        # Retrieve
        res = self.client.get(f"/api/v1/warpings/{new_id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["warpingName"], "Speed Warping")

        # Update
        res = self.client.patch(f"/api/v1/warpings/{new_id}/", {"contactPerson": "Kamran Ali"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["contactPerson"], "Kamran Ali")

        # Delete
        res = self.client.delete(f"/api/v1/warpings/{new_id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_yarn_outcome_warping_dispatch_and_beam_status(self):
        # Create YarnOutcome of type Warping with beamIds
        res = self.client.post("/api/v1/yarn-outcomes/", {
            "yarnIntake": self.intake.id,
            "outcomeType": "Warping",
            "warping": self.warping.id,
            "outcomeBags": 10,
            "outcomeWeightPerBagKg": "45.360",
            "outcomeDate": str(timezone.now().date()),
            "beamIds": [self.beam1.id, self.beam2.id],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        outcome_id = res.data["data"]["id"]

        outcome = YarnOutcome.objects.get(id=outcome_id)
        self.assertEqual(outcome.outcome_type, "Warping")
        self.assertEqual(outcome.status, YarnOutcome.StatusChoices.IN_WARPING)
        self.assertEqual(outcome.warping, self.warping)

        # Check beam statuses transitioned to Warping
        self.beam1.refresh_from_db()
        self.beam2.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.WARPING)
        self.assertEqual(self.beam2.status, Beam.StatusChoices.WARPING)
        self.assertEqual(self.beam1.dispatched_yarn_outcome_id, outcome.id)

    def test_yarn_outcome_warping_validation(self):
        # Warping outcome without warping FK should fail
        res = self.client.post("/api/v1/yarn-outcomes/", {
            "yarnIntake": self.intake.id,
            "outcomeType": "Warping",
            "outcomeBags": 10,
            "outcomeWeightPerBagKg": "45.360",
            "outcomeDate": str(timezone.now().date()),
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("warping", str(res.data.get("errors", res.data)))

    def test_delete_warping_yarn_outcome_reverts_beams(self):
        # Dispatch beams to warping
        outcome = YarnOutcome.objects.create(
            outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            warping=self.warping,
            outcome_bags=10,
            outcome_date=timezone.now().date(),
            status=YarnOutcome.StatusChoices.IN_WARPING,
        )
        from factory.yarn.sizing.services import mark_beams_as_sizing
        mark_beams_as_sizing(outcome, [self.beam1.id, self.beam2.id])

        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.WARPING)

        # Delete outcome
        outcome.delete()

        # Beams should revert to Available
        self.beam1.refresh_from_db()
        self.beam2.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)
        self.assertEqual(self.beam2.status, Beam.StatusChoices.AVAILABLE)
        self.assertIsNone(self.beam1.dispatched_yarn_outcome)

    def test_sizing_outcome_linked_to_warping_yarn_outcome(self):
        # Create Warping dispatch
        outcome = YarnOutcome.objects.create(
            outcome_type=YarnOutcome.OutcomeTypeChoices.WARPING,
            warping=self.warping,
            outcome_bags=20,
            outcome_date=timezone.now().date(),
            status=YarnOutcome.StatusChoices.IN_WARPING,
        )

        # Return set against warping dispatch
        res = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": outcome.id,
            "setNo": "WARP-SET-001",
            "outcomeDate": str(timezone.now().date()),
            "lagatBags": 10,
            "returnBags": 0,
            "remainingBagsOnSizingStock": 10,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        outcome.refresh_from_db()
        self.assertEqual(outcome.status, YarnOutcome.StatusChoices.PARTIALLY_RECEIVED)

        # Complete set return
        res = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": outcome.id,
            "setNo": "WARP-SET-002",
            "outcomeDate": str(timezone.now().date()),
            "lagatBags": 10,
            "returnBags": 0,
            "remainingBagsOnSizingStock": 0,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        outcome.refresh_from_db()
        self.assertEqual(outcome.status, YarnOutcome.StatusChoices.RECEIVED)

        # Filter sizing outcomes by warping
        res = self.client.get(f"/api/v1/sizing-outcomes/?warping={self.warping.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)

        # Warping unit outcomes action
        res = self.client.get(f"/api/v1/warpings/{self.warping.id}/outcomes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 2)
