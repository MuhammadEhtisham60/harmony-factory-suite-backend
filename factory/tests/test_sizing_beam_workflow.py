"""
Comprehensive tests for SizingOutcome and Reusable Beam Assignment Workflow.
Tests:
- Creating SizingOutcome
- Assigning one or multiple existing Beams
- Adding additional Beams to an existing outcome
- Rejecting nonexistent Beam IDs
- Rejecting duplicate Beam IDs
- Rejecting unavailable, damaged, or inactive Beams
- Preventing double active assignment (service & database constraint level)
- Releasing a Beam when ready for reuse and setting status to Available
- Reusing a released Beam in a subsequent SizingOutcome
- Preserving previous assignment history across multiple cycles
- Preventing direct transition of Beam to Available when active assignment exists
- Correct status transitions (ASSIGNED -> IN_USE -> COMPLETED -> RELEASED)
- Transaction rollback if one Beam in a batch is invalid
- YarnOutcome validation (Sizing requires sizing reference; Sold/Weft must be null)
- Permission enforcement (RBAC)
- History and active assignment endpoints
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, Role
from factory.purchase.supplier.models import Supplier
from factory.beam.models import Beam, BeamLoading, Production
from factory.loom.models import Loom
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome



class SizingBeamAssignmentWorkflowTests(APITestCase):

    def setUp(self):
        # Create Superuser (full ERP access)
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",
        )

        # Create Operator user with specific role permissions
        self.operator_role = Role.objects.create(
            name="Sizing Operator",
            slug="sizing-operator",
            status="Active",
            permissions=[
                "sizing.view",
                "sizing.add",
                "sizing.edit",
                "beams.view",
                "beams.assign",
            ],
        )
        self.operator = User.objects.create_user(
            username="operator",
            email="operator@example.com",
            password="operatorpassword123",
            role=self.operator_role,
            status="Active",
        )

        # Create Viewer user with view-only permissions (cannot assign)
        self.viewer_role = Role.objects.create(
            name="Viewer",
            slug="viewer",
            status="Active",
            permissions=["sizing.view", "beams.view"],
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="viewerpassword123",
            role=self.viewer_role,
            status="Active",
        )

        # Authenticate as admin by default
        self.client.force_authenticate(user=self.admin)

        # Create Sizing Unit
        self.sizing = Sizing.objects.create(
            sizing_name="Star Sizing Mills",
            contact_person="Ali Khan",
            phone_no="0300-1234567",
            status="Active",
        )

        # Create Physical Beams
        self.beam1 = Beam.objects.create(
            beam_number="BN-1001",
            yarn_count="20/1",
            warp_count=2400,
            total_ends=2400,
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam2 = Beam.objects.create(
            beam_number="BN-1002",
            yarn_count="20/1",
            warp_count=2400,
            total_ends=2400,
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam3 = Beam.objects.create(
            beam_number="BN-1003",
            yarn_count="20/1",
            warp_count=2400,
            total_ends=2400,
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam_damaged = Beam.objects.create(
            beam_number="BN-DMG",
            status=Beam.StatusChoices.DAMAGED,
        )
        self.beam_inactive = Beam.objects.create(
            beam_number="BN-INA",
            status=Beam.StatusChoices.INACTIVE,
        )

        # Create Supplier & Yarn Intake for yarn outcome testing
        self.supplier = Supplier.objects.create(
            supplier_name="Premier Yarn Mills",
            contact_person="Usman",
            status="Active",
        )
        self.yarn_intake = YarnIntake.objects.create(
            yarn_name="Cotton Warp 20/1",
            yarn_type="Warp",
            yarn_count="20/1",
            supplier=self.supplier,
            bags=100,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_bag=Decimal("15000"),
            intake_date="2026-10-01",
        )

    def test_sizing_entry_complete_crud(self):
        create_response = self.client.post(
            "/api/v1/sizings/",
            {
                "sizingName": "North Sizing Works",
                "address": "12 Mill Road",
                "contactNumber": "0301-5550123",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        sizing_id = create_response.data["data"]["id"]
        self.assertEqual(create_response.data["data"]["contactNumber"], "0301-5550123")
        self.assertEqual(create_response.data["data"]["phoneNo"], "0301-5550123")

        detail_url = f"/api/v1/sizings/{sizing_id}/"
        list_response = self.client.get("/api/v1/sizings/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(item["id"] == sizing_id for item in list_response.data["results"])
        )

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["address"], "12 Mill Road")

        update_response = self.client.put(
            detail_url,
            {
                "sizingName": "North Sizing Factory",
                "address": "18 Mill Road",
                "contactNumber": "0302-5550123",
                "status": "Inactive",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["sizingName"], "North Sizing Factory")

        legacy_phone_response = self.client.patch(
            detail_url, {"phoneNo": "0303-5550123"}, format="json"
        )
        self.assertEqual(legacy_phone_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            legacy_phone_response.data["data"]["contactNumber"], "0303-5550123"
        )

        patch_response = self.client.patch(
            detail_url, {"status": "Active"}, format="json"
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["data"]["status"], "Active")

        invalid_status_response = self.client.patch(
            detail_url, {"status": "Pending"}, format="json"
        )
        self.assertEqual(invalid_status_response.status_code, status.HTTP_400_BAD_REQUEST)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Sizing.objects.filter(id=sizing_id).exists())

    # ── 1. Create SizingOutcome ───────────────────────────────────────────────

    def test_create_sizing_outcome_without_beams(self):
        """Creates a SizingOutcome with no initial beam assignments."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "remarks": "Initial sizing test outcome",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["data"]["totalBeams"], 0)
        self.assertEqual(res.data["data"]["remarks"], "Initial sizing test outcome")

        outcome = SizingOutcome.objects.get(id=res.data["data"]["id"])
        self.assertEqual(outcome.sizing, self.sizing)

    # ── 2. Assign One Existing Beam ───────────────────────────────────────────

    def test_assign_one_existing_beam(self):
        """Assigns one existing available beam to a new SizingOutcome."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "beam_ids": [self.beam1.id],
            "remarks": "Single beam assigned",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["data"]["totalBeams"], 1)

        # Beam status must become SIZING
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.SIZING)

        # Assignment record check
        assignment = SizingBeamAssignment.objects.get(beam=self.beam1)
        self.assertEqual(assignment.status, SizingBeamAssignment.StatusChoices.ASSIGNED)
        self.assertEqual(assignment.sizing_outcome.id, res.data["data"]["id"])

    # ── 3. Assign Multiple Existing Beams ─────────────────────────────────────

    def test_assign_multiple_existing_beams_at_creation(self):
        """Assigns multiple existing Beams (B-001, B-002, B-003) to a SizingOutcome."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "beam_ids": [self.beam1.id, self.beam2.id, self.beam3.id],
            "remarks": "Batch of three beams",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["data"]["totalBeams"], 3)

        # All 3 beams must now have status SIZING
        for b in [self.beam1, self.beam2, self.beam3]:
            b.refresh_from_db()
            self.assertEqual(b.status, Beam.StatusChoices.SIZING)

        # Check nested assignments in response
        assignments = res.data["data"]["beamAssignments"]
        self.assertEqual(len(assignments), 3)
        assigned_numbers = {a["beam"]["beamNumber"] for a in assignments}
        self.assertEqual(assigned_numbers, {"BN-1001", "BN-1002", "BN-1003"})

    # ── 4. Add Additional Beams to an Existing Outcome ────────────────────────

    def test_add_additional_beams_to_existing_outcome(self):
        """Creates an outcome with B-001, then later adds B-002 and B-003."""
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            outcome_date="2026-10-03",
            remarks="Step 1",
        )
        # Assign beam 1
        res1 = self.client.post(
            f"/api/v1/sizing-outcomes/{outcome.id}/assign-beams/",
            {"beam_ids": [self.beam1.id]},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["data"]["totalBeamsAssigned"], 1)

        # Add beam 2 and beam 3
        res2 = self.client.post(
            f"/api/v1/sizing-outcomes/{outcome.id}/assign-beams/",
            {"beam_ids": [self.beam2.id, self.beam3.id]},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["data"]["totalBeamsAssigned"], 3)

        self.beam2.refresh_from_db()
        self.beam3.refresh_from_db()
        self.assertEqual(self.beam2.status, Beam.StatusChoices.SIZING)
        self.assertEqual(self.beam3.status, Beam.StatusChoices.SIZING)

    # ── 5. Reject Nonexistent Beam ID ─────────────────────────────────────────

    def test_reject_nonexistent_beam_id(self):
        """Attempting to assign a nonexistent beam ID must fail with clear error."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "beam_ids": [self.beam1.id, 99999],
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data["success"])
        self.assertIn("beam_ids", res.data["errors"])

        # beam1 must remain AVAILABLE due to atomic rollback
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)
        self.assertFalse(SizingBeamAssignment.objects.filter(beam=self.beam1).exists())

    # ── 6. Reject Duplicate Beam IDs ──────────────────────────────────────────

    def test_reject_duplicate_beam_ids(self):
        """Passing duplicate beam IDs in the payload must fail with validation error."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "beam_ids": [self.beam1.id, self.beam1.id],
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data["success"])

        # No assignments created
        self.assertEqual(SizingBeamAssignment.objects.count(), 0)

    # ── 7. Reject Damaged or Inactive Beams ────────────────────────────────────

    def test_reject_damaged_and_inactive_beams(self):
        """Beams that are DAMAGED or INACTIVE must be rejected."""
        # Damaged
        res_dmg = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam_damaged.id],
            },
            format="json",
        )
        self.assertEqual(res_dmg.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Damaged", str(res_dmg.data))

        # Inactive
        res_ina = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam_inactive.id],
            },
            format="json",
        )
        self.assertEqual(res_ina.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Inactive", str(res_ina.data))

    # ── 8. Prevent Double Active Assignment ───────────────────────────────────

    def test_prevent_double_active_assignment(self):
        """A Beam already assigned cannot be assigned to another SizingOutcome."""
        # First assignment
        res1 = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam1.id],
            },
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Attempt to assign the same beam1 again in a second outcome
        sizing2 = Sizing.objects.create(sizing_name="Second Sizing Unit", status="Active")
        res2 = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": sizing2.id,
                "outcome_date": "2026-10-04",
                "beam_ids": [self.beam1.id, self.beam2.id],
            },
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res2.data["success"])

        # beam2 must remain AVAILABLE because batch rolled back
        self.beam2.refresh_from_db()
        self.assertEqual(self.beam2.status, Beam.StatusChoices.AVAILABLE)

    # ── 9. Transaction Rollback If One Beam In Batch Is Invalid ────────────────

    def test_transaction_rollback_when_one_beam_invalid(self):
        """If 1 beam out of 3 is invalid, no beams are assigned (atomic rollback)."""
        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "beam_ids": [self.beam1.id, self.beam_damaged.id, self.beam2.id],
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify neither beam1 nor beam2 was assigned
        self.beam1.refresh_from_db()
        self.beam2.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)
        self.assertEqual(self.beam2.status, Beam.StatusChoices.AVAILABLE)
        self.assertEqual(SizingBeamAssignment.objects.count(), 0)

    # ── 10. Beam Lifecycle and Valid Status Transitions ───────────────────────

    def test_beam_assignment_lifecycle_transitions(self):
        """
        Tests the transition sequence:
        ASSIGNED (Beam SIZING) -> IN_USE (Beam LOADED) -> COMPLETED (Beam COMPLETED) -> RELEASED (Beam AVAILABLE).
        """
        # Step 1: Assign beam
        outcome = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        self.client.post(
            f"/api/v1/sizing-outcomes/{outcome.id}/assign-beams/",
            {"beam_ids": [self.beam1.id]},
            format="json",
        )
        assignment = SizingBeamAssignment.objects.get(beam=self.beam1)
        self.assertEqual(assignment.status, SizingBeamAssignment.StatusChoices.ASSIGNED)
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.SIZING)

        # Step 2: Transition assignment to IN_USE
        res_in_use = self.client.post(
            f"/api/v1/sizing-beam-assignments/{assignment.id}/transition/",
            {"status": "IN_USE"},
            format="json",
        )
        self.assertEqual(res_in_use.status_code, status.HTTP_200_OK)
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.LOADED)

        # Step 3: Transition assignment to COMPLETED
        res_comp = self.client.post(
            f"/api/v1/sizing-beam-assignments/{assignment.id}/transition/",
            {"status": "COMPLETED"},
            format="json",
        )
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.COMPLETED)

        # Step 4: Release assignment (empty beam)
        res_rel = self.client.post(
            f"/api/v1/sizing-beam-assignments/{assignment.id}/release/",
            format="json",
        )
        self.assertEqual(res_rel.status_code, status.HTTP_200_OK)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, SizingBeamAssignment.StatusChoices.RELEASED)
        self.assertIsNotNone(assignment.released_at)

        # Beam must now be AVAILABLE again for reuse
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)

    # ── 11. Prevent Direct Status Change to Available While Active Assignment Exists ───

    def test_prevent_direct_beam_status_to_available_while_active_assignment(self):
        """Beam status cannot be directly edited to 'Available' if an active assignment exists."""
        outcome = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        self.client.post(
            f"/api/v1/sizing-outcomes/{outcome.id}/assign-beams/",
            {"beam_ids": [self.beam1.id]},
            format="json",
        )

        # Attempt to patch beam status to Available directly via Beam API
        res = self.client.patch(
            f"/api/v1/factory/beams/{self.beam1.id}/",
            {"status": "Available"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active sizing assignment", str(res.data))

    # ── 12. Releasing a Beam via Beam Action ───────────────────────────────────

    def test_release_beam_via_beam_endpoint(self):
        """Tests releasing an active assignment via POST /api/v1/factory/beams/{id}/release/."""
        outcome = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        self.client.post(
            f"/api/v1/sizing-outcomes/{outcome.id}/assign-beams/",
            {"beam_ids": [self.beam1.id]},
            format="json",
        )

        res = self.client.post(f"/api/v1/factory/beams/{self.beam1.id}/release/", format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])

        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)

        assignment = SizingBeamAssignment.objects.get(beam=self.beam1)
        self.assertEqual(assignment.status, SizingBeamAssignment.StatusChoices.RELEASED)
        self.assertIsNotNone(assignment.released_at)

    # ── 13. Reusing a Released Beam in a Different SizingOutcome ──────────────

    def test_reuse_released_beam_in_new_sizing_outcome(self):
        """
        Cycle 1: Sizing #1 -> Outcome #1 -> B-001 assigned, then released.
        Cycle 2: Sizing #2 -> Outcome #2 -> B-001 reused alongside B-002.
        Both historical records must be preserved.
        """
        # Cycle 1
        res1 = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam1.id],
                "remarks": "Cycle 1",
            },
            format="json",
        )
        outcome1_id = res1.data["data"]["id"]

        # Release beam1
        self.client.post(f"/api/v1/factory/beams/{self.beam1.id}/release/", format="json")
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)

        # Cycle 2: assign B-001 again and also B-002
        sizing2 = Sizing.objects.create(sizing_name="Second Sizing Unit", status="Active")
        res2 = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": sizing2.id,
                "outcome_date": "2026-10-15",
                "beam_ids": [self.beam1.id, self.beam2.id],
                "remarks": "Cycle 2 with reused beam",
            },
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        outcome2_id = res2.data["data"]["id"]

        # Verify beam1 has 2 historical assignment records
        beam1_assignments = SizingBeamAssignment.objects.filter(beam=self.beam1).order_by("assigned_at")
        self.assertEqual(beam1_assignments.count(), 2)

        # First assignment is RELEASED, outcome1
        self.assertEqual(beam1_assignments[0].sizing_outcome_id, outcome1_id)
        self.assertEqual(beam1_assignments[0].status, SizingBeamAssignment.StatusChoices.RELEASED)

        # Second assignment is ASSIGNED, outcome2
        self.assertEqual(beam1_assignments[1].sizing_outcome_id, outcome2_id)
        self.assertEqual(beam1_assignments[1].status, SizingBeamAssignment.StatusChoices.ASSIGNED)

    # ── 14. Retrieve Beam Sizing History ──────────────────────────────────────

    def test_get_beam_sizing_history(self):
        """Tests the sizing-history endpoint for a beam across multiple cycles."""
        # Cycle 1
        outcome1 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-01", remarks="C1")
        a1 = SizingBeamAssignment.objects.create(
            sizing_outcome=outcome1, beam=self.beam1, status=SizingBeamAssignment.StatusChoices.RELEASED,
            released_at=timezone.now()
        )
        # Cycle 2
        outcome2 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-10", remarks="C2")
        a2 = SizingBeamAssignment.objects.create(
            sizing_outcome=outcome2, beam=self.beam1, status=SizingBeamAssignment.StatusChoices.ASSIGNED
        )

        res = self.client.get(f"/api/v1/factory/beams/{self.beam1.id}/sizing-history/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["totalSizingCycles"], 2)
        history = res.data["data"]["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["assignmentId"], a2.id)
        self.assertEqual(history[1]["assignmentId"], a1.id)

    # ── 15. Retrieve Active Assignment of a Beam ──────────────────────────────

    def test_get_beam_active_assignment(self):
        """Tests active-assignment endpoint: returns assignment when active, null when released."""
        # Initially no active assignment
        res1 = self.client.get(f"/api/v1/factory/beams/{self.beam1.id}/active-assignment/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIsNone(res1.data["data"])

        # Create active assignment
        outcome = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        assignment = SizingBeamAssignment.objects.create(
            sizing_outcome=outcome, beam=self.beam1, status=SizingBeamAssignment.StatusChoices.ASSIGNED
        )

        res2 = self.client.get(f"/api/v1/factory/beams/{self.beam1.id}/active-assignment/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["data"]["id"], assignment.id)

        # Release assignment -> active-assignment returns None
        assignment.status = SizingBeamAssignment.StatusChoices.RELEASED
        assignment.released_at = timezone.now()
        assignment.save()

        res3 = self.client.get(f"/api/v1/factory/beams/{self.beam1.id}/active-assignment/")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertIsNone(res3.data["data"])

    # ── 16. Retrieve Available Beams Endpoint ─────────────────────────────────

    def test_get_available_beams_endpoint(self):
        """GET /api/v1/factory/beams/available/ returns only AVAILABLE beams."""
        res = self.client.get("/api/v1/factory/beams/available/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data["data"] if "data" in res.data else res.data["results"]
        returned_numbers = {b["beamNumber"] for b in results}
        self.assertIn("BN-1001", returned_numbers)
        self.assertIn("BN-1002", returned_numbers)
        self.assertIn("BN-1003", returned_numbers)
        self.assertNotIn("BN-DMG", returned_numbers)
        self.assertNotIn("BN-INA", returned_numbers)

    # ── 17. Sizing Outcomes for a Sizing Unit ─────────────────────────────────

    def test_list_outcomes_for_sizing(self):
        """GET /api/v1/sizings/{id}/outcomes/ returns all outcomes for that sizing unit."""
        o1 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-01")
        o2 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-02")
        other_sizing = Sizing.objects.create(sizing_name="Other Sizing", status="Active")
        o3 = SizingOutcome.objects.create(sizing=other_sizing, outcome_date="2026-10-03")

        res = self.client.get(f"/api/v1/sizings/{self.sizing.id}/outcomes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data["data"] if "data" in res.data else res.data["results"]
        outcome_ids = {o["id"] for o in data}
        self.assertIn(o1.id, outcome_ids)
        self.assertIn(o2.id, outcome_ids)
        self.assertNotIn(o3.id, outcome_ids)

    # ── 18. YarnOutcome Sizing Validation Requirements ────────────────────────

    def test_yarn_outcome_sizing_validation(self):
        """
        When outcome_type is Sizing, sizing reference is required.
        When outcome_type is Weft or Sold, sizing must be null.
        """
        # Sizing outcome without sizing reference must fail
        invalid_sizing_payload = {
            "yarnIntake": self.yarn_intake.id,
            "outcomeType": "Sizing",
            "outcomeBags": 10,
            "outcomeWeightPerBagKg": "45.360",
            "outcomeDate": "2026-10-03",
        }
        res_fail = self.client.post("/api/v1/yarn-outcomes/", invalid_sizing_payload, format="json")
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sizing", str(res_fail.data["errors"]))

        # Sizing outcome WITH sizing reference succeeds
        valid_sizing_payload = {
            "yarnIntake": self.yarn_intake.id,
            "outcomeType": "Sizing",
            "outcomeBags": 10,
            "outcomeWeightPerBagKg": "45.360",
            "outcomeDate": "2026-10-03",
            "sizing": self.sizing.id,
        }
        res_ok = self.client.post("/api/v1/yarn-outcomes/", valid_sizing_payload, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_201_CREATED)

        # Weft outcome with sizing reference must fail
        invalid_weft_payload = {
            "yarnIntake": self.yarn_intake.id,
            "outcomeType": "Weft",
            "outcomeBags": 5,
            "outcomeWeightPerBagKg": "45.360",
            "outcomeDate": "2026-10-03",
            "sizing": self.sizing.id,
        }
        res_weft_fail = self.client.post("/api/v1/yarn-outcomes/", invalid_weft_payload, format="json")
        self.assertEqual(res_weft_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sizing", str(res_weft_fail.data["errors"]))

    # ── 19. Permission Enforcement ───────────────────────────────────────────

    def test_permission_enforcement(self):
        """
        Viewer (with sizing.view, beams.view) can list outcomes,
        but CANNOT assign beams or create outcomes.
        """
        self.client.force_authenticate(user=self.viewer)

        # Can view outcomes
        res_view = self.client.get("/api/v1/sizing-outcomes/")
        self.assertEqual(res_view.status_code, status.HTTP_200_OK)

        # Cannot create outcome
        res_create = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam1.id],
            },
            format="json",
        )
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

        # Operator (with sizing.add, beams.assign) CAN create and assign
        self.client.force_authenticate(user=self.operator)
        res_op = self.client.post(
            "/api/v1/sizing-outcomes/",
            {
                "sizing_id": self.sizing.id,
                "outcome_date": "2026-10-03",
                "beam_ids": [self.beam1.id],
            },
            format="json",
        )
        self.assertEqual(res_op.status_code, status.HTTP_201_CREATED)

    # ── 20. Concurrent Assignment Attempts & Constraint Verification ──────────

    def test_database_unique_active_constraint_prevents_concurrent_assignment(self):
        """
        Database-level conditional unique constraint (unique_active_sizing_assignment_per_beam)
        guarantees that even if two transactions bypassed application checks,
        the database rejects overlapping active (ASSIGNED/IN_USE) assignments with IntegrityError.
        """
        from django.db import IntegrityError

        outcome1 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        outcome2 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-04")

        # First active assignment succeeds
        SizingBeamAssignment.objects.create(
            sizing_outcome=outcome1,
            beam=self.beam1,
            status=SizingBeamAssignment.StatusChoices.ASSIGNED,
        )

        # Second active assignment for the same beam MUST trigger database IntegrityError
        with self.assertRaises(IntegrityError):
            SizingBeamAssignment.objects.create(
                sizing_outcome=outcome2,
                beam=self.beam1,
                status=SizingBeamAssignment.StatusChoices.IN_USE,
            )

    def test_service_layer_select_for_update_handles_concurrent_race(self):
        """
        Simulate a concurrent scenario: Thread A locks and changes beam status to SIZING.
        Thread B attempts to assign: assign_beams_to_outcome detects the status change and raises ValidationError.
        """
        from rest_framework.exceptions import ValidationError
        from factory.yarn.sizing.services import assign_beams_to_outcome

        outcome1 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-03")
        outcome2 = SizingOutcome.objects.create(sizing=self.sizing, outcome_date="2026-10-04")

        # First assignment succeeds
        assign_beams_to_outcome(outcome1, [self.beam1.id])

        # Second concurrent attempt detects beam is now SIZING
        with self.assertRaises(ValidationError) as ctx:
            assign_beams_to_outcome(outcome2, [self.beam1.id])
        self.assertIn("cannot be assigned", str(ctx.exception))


class BeamLoadingAndProductionWorkflowTests(APITestCase):
    """
    Tests for the complete factory workflow:
    Sizing -> Sizing Outcome -> Beam Loading -> Loom -> Production -> Beam Empty -> Available -> Reuse
    """

    def setUp(self):
        # Create Superuser
        self.admin = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="adminpassword123",
        )

        # Create Operator
        self.operator_role = Role.objects.create(
            name="Weaving Operator",
            slug="weaving-operator",
            status="Active",
            permissions=[
                "sizing.view",
                "sizing.add",
                "sizing.edit",
                "beams.view",
                "beams.assign",
                "beams.edit",
                "looms.view",
                "looms.production",
                "looms.assign_beam",
            ],
        )
        self.operator = User.objects.create_user(
            username="operator2",
            email="operator2@example.com",
            password="operatorpassword123",
            role=self.operator_role,
            status="Active",
        )

        self.client.force_authenticate(user=self.admin)

        # Create Sizing Unit
        self.sizing = Sizing.objects.create(
            sizing_name="Standard Sizing Works",
            contact_person="Babar",
            phone_no="0321-7654321",
            status="Active",
        )

        # Create Beams (reusable physical assets)
        self.beam1 = Beam.objects.create(
            beam_number="BEAM-01",
            yarn_count="40/1",
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam2 = Beam.objects.create(
            beam_number="BEAM-02",
            yarn_count="40/1",
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam3 = Beam.objects.create(
            beam_number="BEAM-03",
            yarn_count="40/1",
            status=Beam.StatusChoices.AVAILABLE,
        )
        self.beam_loaded = Beam.objects.create(
            beam_number="BEAM-LOADED",
            status=Beam.StatusChoices.LOADED,
        )

        # Create Looms
        self.loom1 = Loom.objects.create(
            loom_code="L-101",
            loom_name="Airjet Loom 101",
            status=Loom.StatusChoices.ACTIVE,
        )
        self.loom2 = Loom.objects.create(
            loom_code="L-102",
            loom_name="Airjet Loom 102",
            status=Loom.StatusChoices.ACTIVE,
        )
        self.loom3 = Loom.objects.create(
            loom_code="L-103",
            loom_name="Airjet Loom 103",
            status=Loom.StatusChoices.ACTIVE,
        )

    # ── TEST 1: Create SizingOutcome successfully ─────────────────────────────
    def test_1_create_sizing_outcome_successfully(self):
        """
        TEST 1: Create SizingOutcome successfully with all 24 required fields.
        SizingOutcome represents "Return of the Set from Sizing" and does NOT create a new Beam.
        """
        initial_beam_count = Beam.objects.count()

        payload = {
            "sizing_id": self.sizing.id,
            "outcome_date": "2026-10-03",
            "set_no": "SET-2026-001",
            "sizing_name": "Standard Sizing Works",
            "total_bags_on_sizing": 50,
            "bag_packing_cone": 24,
            "total_cones": 1200,
            "remaining_bags_on_sizing_stock": 5,
            "remaining_cones_on_sizing_stock": 120,
            "lagat_bags": 45,
            "lagat_cones": 1080,
            "brand": "Diamond Yarn",
            "width": "63.00",
            "set_length_meter": "12500.00",
            "set_length_gaz": "13670.17",
            "total_tarr": "4800.00",
            "yarn_beam": "YB-SetA",
            "back_beam": "BB-SetA",
            "count": "40/1",
            "total_set_lumbai": "12500.00",
            "total_set_shortage": "2.50",
            "remarks": "Set returned in good condition",
        }

        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        data = res.data["data"]

        self.assertEqual(data["setNo"], "SET-2026-001")
        self.assertEqual(data["sizingName"], "Standard Sizing Works")
        self.assertEqual(data["totalBagsOnSizing"], 50)
        self.assertEqual(Decimal(str(data["lagatBags"])), Decimal("45.00"))
        self.assertEqual(data["brand"], "Diamond Yarn")
        self.assertEqual(data["count"], "40/1")


        # Crucial check: verify SizingOutcome did NOT directly create any new Beam record!
        self.assertEqual(Beam.objects.count(), initial_beam_count)

        # Database verification
        outcome = SizingOutcome.objects.get(id=data["id"])
        self.assertEqual(outcome.set_no, "SET-2026-001")
        self.assertEqual(outcome.lagat_bags, 45)
        self.assertEqual(outcome.total_tarr, Decimal("4800.00"))

    # ── TEST 2: Create one BeamLoading for one SizingOutcome ───────────────────
    def test_2_create_one_beam_loading_for_one_sizing_outcome(self):
        """
        TEST 2: Create one BeamLoading record connecting SizingOutcome -> existing Beam -> Loom.
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-10",
            outcome_date="2026-10-03",
        )

        payload = {
            "sizing_outcome": outcome.id,
            "beam": self.beam1.id,
            "loom": self.loom1.id,
            "warp_count": "40/1",
            "weft_count": "40/1",
            "reed_width": "63.00",
            "pick": "68.00",
            "reed_count": "72.00",
            "pick_count": "68.00",
            "shortage": "2.50",
            "width": "63.00",
            "lakhai": "450.00",
            "installation_date": "2026-10-03",
        }

        res = self.client.post("/api/v1/factory/beam-loadings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        data = res.data["data"]

        self.assertEqual(data["setNo"], "SET-10")
        self.assertEqual(data["beamNumber"], "BEAM-01")
        self.assertEqual(data["loomCode"], "L-101")
        self.assertEqual(data["warpCount"], "40/1")
        self.assertEqual(data["status"], BeamLoading.StatusChoices.LOADED)

        loading = BeamLoading.objects.get(id=data["id"])
        self.assertEqual(loading.sizing_outcome, outcome)
        self.assertEqual(loading.beam, self.beam1)
        self.assertEqual(loading.loom, self.loom1)

    # ── TEST 3: Create multiple BeamLoadings for one SizingOutcome ─────────────
    def test_3_create_multiple_beam_loadings_for_one_sizing_outcome(self):
        """
        TEST 3: Create multiple BeamLoadings for one SizingOutcome.
        Example:
        SizingOutcome #10 -> Beam #1 (Loom 1), Beam #2 (Loom 2), Beam #3 (Loom 3).
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-BATCH-10",
            outcome_date="2026-10-03",
        )

        # Batch loading endpoint
        batch_payload = {
            "sizing_outcome": outcome.id,
            "loadings": [
                {
                    "beam_id": self.beam1.id,
                    "loom_id": self.loom1.id,
                    "installation_date": "2026-10-03",
                    "warp_count": "40/1",
                    "pick": "68.00",
                },
                {
                    "beam_id": self.beam2.id,
                    "loom_id": self.loom2.id,
                    "installation_date": "2026-10-03",
                    "warp_count": "40/1",
                    "pick": "68.00",
                },
                {
                    "beam_id": self.beam3.id,
                    "loom_id": self.loom3.id,
                    "installation_date": "2026-10-03",
                    "warp_count": "40/1",
                    "pick": "68.00",
                },
            ]
        }

        res = self.client.post("/api/v1/factory/beam-loadings/batch/", batch_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(len(res.data["data"]), 3)

        # All 3 records belong to SizingOutcome #10
        loadings = BeamLoading.objects.filter(sizing_outcome=outcome)
        self.assertEqual(loadings.count(), 3)
        loaded_beams = {l.beam_id for l in loadings}
        self.assertEqual(loaded_beams, {self.beam1.id, self.beam2.id, self.beam3.id})

        # All 3 beams are now LOADED
        for b in [self.beam1, self.beam2, self.beam3]:
            b.refresh_from_db()
            self.assertEqual(b.status, Beam.StatusChoices.LOADED)

    # ── TEST 4: Try loading a Beam whose status is not AVAILABLE ───────────────
    def test_4_try_loading_beam_whose_status_is_not_available(self):
        """
        TEST 4: Try loading a Beam whose status is not AVAILABLE.
        Expected: Request rejected with HTTP 400 Bad Request.
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-UNAVAIL",
            outcome_date="2026-10-03",
        )

        payload = {
            "sizing_outcome": outcome.id,
            "beam": self.beam_loaded.id,  # Status is LOADED, not AVAILABLE
            "loom": self.loom1.id,
            "installation_date": "2026-10-03",
        }

        res = self.client.post("/api/v1/factory/beam-loadings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Available", str(res.data))

        # No loading created
        self.assertFalse(BeamLoading.objects.filter(beam=self.beam_loaded).exists())

    # ── TEST 5: After BeamLoading is created, Beam.status == LOADED ────────────
    def test_5_after_beam_loading_is_created_beam_status_is_loaded(self):
        """
        TEST 5: After BeamLoading is created, physical Beam status must be LOADED,
        and Loom status must be PRODUCTION.
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-55",
            outcome_date="2026-10-03",
        )

        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)
        self.assertEqual(self.loom1.status, Loom.StatusChoices.ACTIVE)

        res = self.client.post("/api/v1/factory/beam-loadings/", {
            "sizing_outcome": outcome.id,
            "beam": self.beam1.id,
            "loom": self.loom1.id,
            "installation_date": "2026-10-03",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.LOADED)

        self.loom1.refresh_from_db()
        self.assertEqual(self.loom1.status, Loom.StatusChoices.PRODUCTION)

    # ── TEST 6: Production changes Beam to IN_PRODUCTION ──────────────────────
    def test_6_production_changes_beam_to_in_production(self):
        """
        TEST 6: Production records daily cloth meters produced and advances
        Beam.status and BeamLoading.status to IN_PRODUCTION.
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-PROD",
            outcome_date="2026-10-03",
        )
        loading = BeamLoading.objects.create(
            sizing_outcome=outcome,
            beam=self.beam1,
            loom=self.loom1,
            installation_date="2026-10-03",
            status=BeamLoading.StatusChoices.LOADED,
        )
        self.beam1.status = Beam.StatusChoices.LOADED
        self.beam1.save()
        self.loom1.status = Loom.StatusChoices.PRODUCTION
        self.loom1.save()


        # Log daily production entry
        payload = {
            "beam_loading": loading.id,
            "production_date": "2026-10-04",
            "meters_produced": "620.50",
            "shift": "Morning",
            "operator_name": "Akram Weaver",
            "remarks": "Smooth run, no warp breaks",
            "beam_emptied": False,
        }

        res = self.client.post("/api/v1/factory/productions/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        # Beam must now be IN_PRODUCTION
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.IN_PRODUCTION)

        # Loading must now be IN_PRODUCTION
        loading.refresh_from_db()
        self.assertEqual(loading.status, BeamLoading.StatusChoices.IN_PRODUCTION)

        # Loom remains in PRODUCTION
        self.loom1.refresh_from_db()
        self.assertEqual(self.loom1.status, Loom.StatusChoices.PRODUCTION)

    # ── TEST 7: When Beam becomes physically empty, Beam.status == AVAILABLE ──
    def test_7_when_beam_becomes_physically_empty_beam_status_is_available(self):
        """
        TEST 7: When production confirms that the Beam is physically empty (beam_emptied=True),
        or via explicit empty action:
        Beam.status becomes AVAILABLE.
        BeamLoading.status becomes COMPLETED.
        Loom.status becomes ACTIVE.
        """
        outcome = SizingOutcome.objects.create(
            sizing=self.sizing,
            set_no="SET-EMPTY",
            outcome_date="2026-10-03",
        )
        loading = BeamLoading.objects.create(
            sizing_outcome=outcome,
            beam=self.beam1,
            loom=self.loom1,
            installation_date="2026-10-03",
            status=BeamLoading.StatusChoices.IN_PRODUCTION,
        )
        self.beam1.status = Beam.StatusChoices.IN_PRODUCTION
        self.beam1.save()
        self.loom1.status = Loom.StatusChoices.PRODUCTION
        self.loom1.save()


        # Production with beam_emptied=True
        prod_payload = {
            "beam_loading": loading.id,
            "production_date": "2026-10-05",
            "meters_produced": "150.00",
            "shift": "Night",
            "operator_name": "Tahir",
            "remarks": "Final cut - Beam is empty",
            "beam_emptied": True,
        }

        res = self.client.post("/api/v1/factory/productions/", prod_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Physical beam is now AVAILABLE for reuse!
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)

        # Loading record is COMPLETED
        loading.refresh_from_db()
        self.assertEqual(loading.status, BeamLoading.StatusChoices.COMPLETED)

        # Loom is now ACTIVE and free for another beam
        self.loom1.refresh_from_db()
        self.assertEqual(self.loom1.status, Loom.StatusChoices.ACTIVE)

    # ── TEST 8: Reuse the same Beam for another SizingOutcome ─────────────────
    def test_8_reuse_same_beam_for_another_sizing_outcome(self):
        """
        TEST 8: Reuse the same Beam for another SizingOutcome.
        Expected:
        - Old BeamLoading remains intact in database (history preserved).
        - New BeamLoading is created for the new SizingOutcome.
        - Physical Beam record is reused (NO new Beam is created).
        """
        initial_beam_pk = self.beam1.id
        total_beams_before = Beam.objects.count()

        # Outcome A (First cycle)
        outcome_a = SizingOutcome.objects.create(
            sizing=self.sizing, set_no="SET-A", outcome_date="2026-10-01"
        )
        res_load_a = self.client.post("/api/v1/factory/beam-loadings/", {
            "sizing_outcome": outcome_a.id,
            "beam": self.beam1.id,
            "loom": self.loom1.id,
            "installation_date": "2026-10-01",
        }, format="json")
        self.assertEqual(res_load_a.status_code, status.HTTP_201_CREATED)
        loading_a_id = res_load_a.data["data"]["id"]

        # Production finishes and empties Beam 1
        self.client.post("/api/v1/factory/productions/", {
            "beam_loading": loading_a_id,
            "production_date": "2026-10-05",
            "meters_produced": "2000.00",
            "beam_emptied": True,
        }, format="json")

        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.status, Beam.StatusChoices.AVAILABLE)

        # Outcome B (Second cycle)
        outcome_b = SizingOutcome.objects.create(
            sizing=self.sizing, set_no="SET-B", outcome_date="2026-10-10"
        )
        res_load_b = self.client.post("/api/v1/factory/beam-loadings/", {
            "sizing_outcome": outcome_b.id,
            "beam": self.beam1.id,  # REUSING THE EXACT SAME BEAM RECORD!
            "loom": self.loom2.id,
            "installation_date": "2026-10-10",
        }, format="json")
        self.assertEqual(res_load_b.status_code, status.HTTP_201_CREATED)
        loading_b_id = res_load_b.data["data"]["id"]

        # Assert no new Beam was created: same physical beam was reused
        self.assertEqual(Beam.objects.count(), total_beams_before)
        self.beam1.refresh_from_db()
        self.assertEqual(self.beam1.id, initial_beam_pk)
        self.assertEqual(self.beam1.status, Beam.StatusChoices.LOADED)

        # Both BeamLoading records exist and belong to the same beam
        beam_loadings = BeamLoading.objects.filter(beam=self.beam1).order_by("installation_date")
        self.assertEqual(beam_loadings.count(), 2)

        # Old BeamLoading remains intact
        loading_a = beam_loadings[0]
        self.assertEqual(loading_a.id, loading_a_id)
        self.assertEqual(loading_a.sizing_outcome, outcome_a)
        self.assertEqual(loading_a.loom, self.loom1)
        self.assertEqual(loading_a.status, BeamLoading.StatusChoices.COMPLETED)

        # New BeamLoading is created
        loading_b = beam_loadings[1]
        self.assertEqual(loading_b.id, loading_b_id)
        self.assertEqual(loading_b.sizing_outcome, outcome_b)
        self.assertEqual(loading_b.loom, self.loom2)
        self.assertEqual(loading_b.status, BeamLoading.StatusChoices.LOADED)

    # ── TEST 9: Verify Beam history contains both loading records ─────────────
    def test_9_verify_beam_history_contains_both_loading_records(self):
        """
        TEST 9: Verify Beam history endpoint contains both loading records.
        """
        outcome_a = SizingOutcome.objects.create(sizing=self.sizing, set_no="SET-HIST-A", outcome_date="2026-01-10")
        loading_a = BeamLoading.objects.create(
            sizing_outcome=outcome_a,
            beam=self.beam1,
            loom=self.loom1,
            installation_date="2026-01-10",
            status=BeamLoading.StatusChoices.COMPLETED,
        )

        outcome_b = SizingOutcome.objects.create(sizing=self.sizing, set_no="SET-HIST-B", outcome_date="2026-06-15")
        loading_b = BeamLoading.objects.create(
            sizing_outcome=outcome_b,
            beam=self.beam1,
            loom=self.loom2,
            installation_date="2026-06-15",
            status=BeamLoading.StatusChoices.LOADED,
        )

        # Query history via BeamViewSet action
        res = self.client.get(f"/api/v1/factory/beams/{self.beam1.id}/loading-history/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data["data"]

        self.assertEqual(data["beamId"], self.beam1.id)
        self.assertEqual(data["beamNumber"], "BEAM-01")
        self.assertEqual(data["totalLoadings"], 2)
        self.assertEqual(len(data["history"]), 2)

        history_ids = [h["id"] for h in data["history"]]
        self.assertIn(loading_a.id, history_ids)
        self.assertIn(loading_b.id, history_ids)

        # Also query history via filterable BeamLoadingViewSet
        res_filter = self.client.get(f"/api/v1/factory/beam-loadings/?beam={self.beam1.id}")
        self.assertEqual(res_filter.status_code, status.HTTP_200_OK)
        results = res_filter.data["results"] if "results" in res_filter.data else res_filter.data["data"]
        self.assertEqual(len(results), 2)



