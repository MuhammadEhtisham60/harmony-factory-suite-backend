"""
Tests for SizingOutcome status management and payment fields:
1. YarnOutcome status transitions ("In Sizing", "Partially Received", "Received")
2. Serializer fields: isReceived, isPartiallyReceived, yarnOutcomeStatus
3. Payment fields: amount_paid, amount_due, payment_status ("Unpaid", "Partially Paid", "Paid")
4. Dynamic recalculation on creation, update, and deletion
5. Filtering by payment_status
6. High precision decimal preservation without rounding
"""

from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.purchase.supplier.models import Supplier
from factory.yarn.sizing.models import Sizing, SizingOutcome
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome

D = Decimal


class SizingOutcomeStatusAndPaymentTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="sizing_admin",
            email="sizing_admin@example.com",
            password="admin-pw-12345"
        )
        self.client.force_authenticate(user=self.admin)

        self.supplier = Supplier.objects.create(supplier_name="Premium Yarn Ltd", status="Active")
        self.intake = YarnIntake.objects.create(
            yarn_name="Cotton 30/1 Carded",
            yarn_type="Carded",
            yarn_count="30/1",
            supplier=self.supplier,
            bags=100,
            cones_per_bag=24,
            weight_per_bag_kg=D("45.360000"),
            rate_per_lb=D("200.000000"),
            intake_date="2026-10-01",
        )

        self.sizing = Sizing.objects.create(
            sizing_name="Star Sizing Mill",
            contact_person="Tariq Mahmood",
            phone_no="0300-7654321",
            status="Active",
        )

        # Dispatch 20 bags to sizing
        self.yarn_outcome = YarnOutcome.objects.create(
            yarn_intake=self.intake,
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing=self.sizing,
            outcome_bags=20,
            outcome_cones_per_bag=24,
            outcome_weight_per_bag_kg=D("45.360000"),
            outcome_weight_kg=D("907.200000"),
            outcome_weight_lb=D("2000.000000"),
            outcome_date="2026-10-02",
            status=YarnOutcome.StatusChoices.IN_SIZING,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 1. STATUS TRANSITION TESTS
    # ──────────────────────────────────────────────────────────────────────────

    def test_partial_receipt_sets_partially_received_status(self):
        """When lagat_bags < outcome_bags, yarn outcome status must be Partially Received."""
        payload = {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "setNo": "SET-P1",
            "setBill": "BILL-P1",
            "lagatBags": "8.500000",
            "lagatCones": "204.000000",
            "ratePerKg": "15.000000",
            "netWeightKg": "100.000000",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

        # YarnOutcome in database must be Partially Received
        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Partially Received")

        # Returned sizing outcome data must reflect yarnOutcomeStatus
        self.assertEqual(res.data["data"]["yarnOutcomeStatus"], "Partially Received")
        self.assertEqual(res.data["data"]["yarnOutcomeDetail"]["status"], "Partially Received")

        # Yarn Outcome API endpoint must return status, isReceived=False, isPartiallyReceived=True
        res_yo = self.client.get(f"/api/v1/yarn-outcomes/{self.yarn_outcome.id}/")
        self.assertEqual(res_yo.status_code, status.HTTP_200_OK)
        self.assertEqual(res_yo.data["data"]["status"], "Partially Received")
        self.assertFalse(res_yo.data["data"]["isReceived"])
        self.assertTrue(res_yo.data["data"]["isPartiallyReceived"])

    def test_full_receipt_sets_received_status(self):
        """When total lagat_bags equals or exceeds outcome_bags, status becomes Received."""
        # 1st outcome: 12 bags (Partially Received)
        self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "lagatBags": "12.000000",
            "ratePerKg": "15.000000",
            "netWeightKg": "100.000000",
        }, format="json")
        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Partially Received")

        # 2nd outcome: 8 bags (Total = 20 == outcome_bags -> Received)
        res2 = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-07",
            "lagatBags": "8.000000",
            "ratePerKg": "15.000000",
            "netWeightKg": "100.000000",
        }, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Received")
        self.assertEqual(res2.data["data"]["yarnOutcomeStatus"], "Received")

        # Check Yarn Outcome endpoint
        res_yo = self.client.get(f"/api/v1/yarn-outcomes/{self.yarn_outcome.id}/")
        self.assertEqual(res_yo.data["data"]["status"], "Received")
        self.assertTrue(res_yo.data["data"]["isReceived"])
        self.assertFalse(res_yo.data["data"]["isPartiallyReceived"])

    def test_remaining_stock_keeps_partially_received(self):
        """If remaining_bags_on_sizing_stock > 0, status must remain Partially Received."""
        payload = {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-06",
            "lagatBags": "20.000000",
            "remainingBagsOnSizingStock": 3,
            "ratePerKg": "10.000000",
            "netWeightKg": "200.000000",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Partially Received")

    def test_updating_sizing_outcome_recalculates_status(self):
        """Updating lagat_bags recalculates yarn outcome status dynamically."""
        res = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-06",
            "lagatBags": "20.000000",
            "ratePerKg": "10.000000",
            "netWeightKg": "100.000000",
        }, format="json")
        so_id = res.data["data"]["id"]
        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Received")

        # Update lagat bags down to 10
        patch_res = self.client.patch(f"/api/v1/sizing-outcomes/{so_id}/", {
            "lagatBags": "10.000000"
        }, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Partially Received")

    def test_deleting_sizing_outcome_recalculates_status(self):
        """Deleting sizing outcome restores status to Partially Received or In Sizing."""
        res1 = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-06",
            "lagatBags": "10.000000",
        }, format="json")
        so1_id = res1.data["data"]["id"]

        res2 = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-07",
            "lagatBags": "10.000000",
        }, format="json")
        so2_id = res2.data["data"]["id"]

        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Received")

        # Delete so2 -> only 10 bags left out of 20 -> Partially Received
        del_res = self.client.delete(f"/api/v1/sizing-outcomes/{so2_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "Partially Received")

        # Delete so1 -> 0 outcomes remain -> In Sizing
        del_res2 = self.client.delete(f"/api/v1/sizing-outcomes/{so1_id}/")
        self.assertEqual(del_res2.status_code, status.HTTP_200_OK)
        self.yarn_outcome.refresh_from_db()
        self.assertEqual(self.yarn_outcome.status, "In Sizing")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. PAYMENT FIELDS & CALCULATION TESTS
    # ──────────────────────────────────────────────────────────────────────────

    def test_amount_paid_and_due_unpaid_by_default(self):
        """When created without amountPaid, default is 0 paid, amount_due = total_rate, status Unpaid."""
        payload = {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "ratePerKg": "25.500000",
            "netWeightKg": "100.000000",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data["data"]

        # 100 * 25.5 = 2550
        self.assertEqual(D(data["totalRate"]), D("2550.000000"))
        self.assertEqual(D(data["amountPaid"]), D("0.000000"))
        self.assertEqual(D(data["amountDue"]), D("2550.000000"))
        self.assertEqual(data["paymentStatus"], "Unpaid")

    def test_amount_paid_partially_paid(self):
        """When 0 < amountPaid < totalRate, paymentStatus must be Partially Paid and amountDue = totalRate - amountPaid."""
        payload = {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "ratePerKg": "20.000000",
            "netWeightKg": "100.000000",  # total_rate = 2000
            "amountPaid": "750.500000",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data["data"]

        self.assertEqual(D(data["totalRate"]), D("2000.000000"))
        self.assertEqual(D(data["amountPaid"]), D("750.500000"))
        self.assertEqual(D(data["amountDue"]), D("1249.500000"))
        self.assertEqual(data["paymentStatus"], "Partially Paid")

    def test_amount_paid_fully_paid(self):
        """When amountPaid >= totalRate, paymentStatus must be Paid and amountDue = 0."""
        payload = {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "ratePerKg": "20.000000",
            "netWeightKg": "100.000000",
            "amountPaid": "2000.000000",
        }
        res = self.client.post("/api/v1/sizing-outcomes/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data["data"]

        self.assertEqual(D(data["totalRate"]), D("2000.000000"))
        self.assertEqual(D(data["amountPaid"]), D("2000.000000"))
        self.assertEqual(D(data["amountDue"]), D("0.000000"))
        self.assertEqual(data["paymentStatus"], "Paid")

    def test_patch_amount_paid_recalculates_due_and_status(self):
        """Updating amountPaid via PATCH recalculates amountDue and paymentStatus automatically."""
        # Initial: total = 3000, paid = 0, due = 3000, Unpaid
        res = self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "ratePerKg": "30.000000",
            "netWeightKg": "100.000000",
        }, format="json")
        so_id = res.data["data"]["id"]

        # Step 1: Pay 1000 -> Partially Paid, due = 2000
        p1 = self.client.patch(f"/api/v1/sizing-outcomes/{so_id}/", {
            "amountPaid": "1000.000000"
        }, format="json")
        self.assertEqual(p1.status_code, status.HTTP_200_OK)
        self.assertEqual(D(p1.data["data"]["amountPaid"]), D("1000.000000"))
        self.assertEqual(D(p1.data["data"]["amountDue"]), D("2000.000000"))
        self.assertEqual(p1.data["data"]["paymentStatus"], "Partially Paid")

        # Step 2: Pay full 3000 -> Paid, due = 0
        p2 = self.client.patch(f"/api/v1/sizing-outcomes/{so_id}/", {
            "amountPaid": "3000.000000"
        }, format="json")
        self.assertEqual(p2.status_code, status.HTTP_200_OK)
        self.assertEqual(D(p2.data["data"]["amountPaid"]), D("3000.000000"))
        self.assertEqual(D(p2.data["data"]["amountDue"]), D("0.000000"))
        self.assertEqual(p2.data["data"]["paymentStatus"], "Paid")

    def test_filter_by_payment_status(self):
        """Test GET /api/v1/sizing-outcomes/?payment_status=Unpaid and Paid."""
        # Unpaid
        self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-05",
            "ratePerKg": "10.000000",
            "netWeightKg": "10.000000",
            "amountPaid": "0",
        }, format="json")

        # Paid
        self.client.post("/api/v1/sizing-outcomes/", {
            "yarnOutcomeId": self.yarn_outcome.id,
            "outcomeDate": "2026-10-06",
            "ratePerKg": "10.000000",
            "netWeightKg": "10.000000",
            "amountPaid": "100.000000",
        }, format="json")

        res_unpaid = self.client.get("/api/v1/sizing-outcomes/?payment_status=Unpaid")
        self.assertEqual(res_unpaid.status_code, status.HTTP_200_OK)
        for item in res_unpaid.data.get("results", []):
            self.assertEqual(item["paymentStatus"], "Unpaid")

        res_paid = self.client.get("/api/v1/sizing-outcomes/?payment_status=Paid")
        self.assertEqual(res_paid.status_code, status.HTTP_200_OK)
        for item in res_paid.data.get("results", []):
            self.assertEqual(item["paymentStatus"], "Paid")

    def test_high_precision_decimals_in_payment_calculations(self):
        """Strict precision: exact 6-decimal rate and weight calculations without rounding."""
        rate = D("12.345678")
        net = D("98.765432")
        expected_total = rate * net  # 1219.326221002896
        paid = D("500.123456")
        expected_due = expected_total - paid

        so = SizingOutcome.objects.create(
            yarn_outcome=self.yarn_outcome,
            outcome_date="2026-10-08",
            rate_per_kg=rate,
            net_weight_kg=net,
            amount_paid=paid,
        )
        so.refresh_from_db()

        self.assertEqual(so.payment_status, "Partially Paid")
        self.assertEqual(so.total_rate, D("1219.326221"))
        self.assertEqual(so.amount_paid, paid)
        self.assertEqual(so.amount_due, D("719.202765"))
