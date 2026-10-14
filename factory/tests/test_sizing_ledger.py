"""
Comprehensive tests for Sizing Ledger APIs:
1. Main Sizing Ledger API (/api/v1/sizing-ledger/)
2. Individual Sizing Detail Ledger API (/api/v1/sizing-ledger/{id}/ and /api/v1/sizings/{id}/ledger/)
3. Transaction-level ledger stream (/api/v1/sizing-ledger/transactions/)
4. Calculations: totalBoxesSent, totalBoxesReceived, totalBoxesBalance, totalPayables
5. Aggregate counters across the entire filtered dataset (not just the current page)
6. Zero cartesian join duplication
7. Full Decimal precision without quantization
8. Date-range, search, status, and ordering filters
9. Opening balance calculations
10. Permissions and error validation (400 on invalid ID, 404 on nonexistent ID, 403 on unauthorized)
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from factory.purchase.supplier.models import Supplier
from factory.yarn.sizing.models import Sizing, SizingOutcome
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome
from factory.yarn.yarn_stock.models import LB_PER_KG

URL = "/api/v1/sizing-ledger/"
D = Decimal


class SizingLedgerTests(APITestCase):
    WEIGHT_PER_BAG = D("45.123457")

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="ledger_admin", email="ledger_admin@example.com", password="pw-12345-abc"
        )
        self.client.force_authenticate(user=self.admin)

        supplier = Supplier.objects.create(supplier_name="Ledger Yarn Mills", status="Active")
        self.intake = YarnIntake.objects.create(
            yarn_name="Cotton Warp 20/1",
            yarn_type="Warp",
            yarn_count="20/1",
            supplier=supplier,
            bags=500,
            cones_per_bag=24,
            weight_per_bag_kg=D("45.36"),
            rate_per_lb=D("150"),
            intake_date="2026-10-01",
        )

        self.sizing_a = Sizing.objects.create(
            sizing_name="Alpha Sizing",
            contact_person="Ali Khan",
            phone_no="0300-1111111",
            email="alpha@example.com",
            address="Faisalabad Sector 1",
            status="Active",
        )
        self.sizing_b = Sizing.objects.create(
            sizing_name="Beta Sizing",
            contact_person="Bilal Ahmed",
            phone_no="0300-2222222",
            email="beta@example.com",
            address="Faisalabad Sector 2",
            status="Active",
        )

        # ── Sizing A transactions: IN, OUT, IN, OUT ──────────────────────────
        self.yo1 = self._yarn_out(self.sizing_a, bags=10, date="2026-10-02")
        self.so1 = self._sizing_out(
            self.yo1,
            date="2026-10-05",
            lagat_bags="3.333333",
            lagat_cones="80.000001",
            rate="12.345678",
            net="98.765432",
            set_no="SET-1",
            set_bill="B-1",
        )
        self.yo2 = self._yarn_out(self.sizing_a, bags=5, date="2026-10-10")
        self.so2 = self._sizing_out(
            self.yo2,
            date="2026-10-12",
            lagat_bags="1.5",
            lagat_cones="36",
            rate="10",
            net="50.5",
            set_no="SET-2",
            set_bill="B-2",
        )
        self.so1.refresh_from_db()
        self.so2.refresh_from_db()


    # ── fixture helpers ───────────────────────────────────────────────────

    def _yarn_out(self, sizing, bags, date, per_bag=None, cones_per_bag=24):
        return YarnOutcome.objects.create(
            yarn_intake=self.intake,
            outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
            sizing=sizing,
            outcome_bags=bags,
            outcome_cones_per_bag=cones_per_bag,
            outcome_weight_per_bag_kg=per_bag or self.WEIGHT_PER_BAG,
            outcome_date=date,
        )

    def _sizing_out(self, yarn_outcome, date, lagat_bags, lagat_cones, rate, net, set_no="", set_bill=""):
        return SizingOutcome.objects.create(
            yarn_outcome=yarn_outcome,
            outcome_date=date,
            lagat_bags=D(lagat_bags),
            lagat_cones=D(lagat_cones),
            rate_per_kg=D(rate),
            net_weight_kg=D(net),
            set_no=set_no,
            set_bill=set_bill,
        )

    # ── 1. Main Sizing Ledger API ─────────────────────────────────────────

    def test_01_main_sizing_ledger_returns_all_sizing_records_with_aggregate_totals(self):
        """B: Main Sizing Ledger returns all sizing records, per-sizing counters, and top-level aggregates."""
        res = self.client.get(URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["count"], 2)

        results = res.data["results"]
        self.assertEqual(len(results), 2)

        # Expected totals for Sizing A:
        # Sent: 10 + 5 = 15 bags
        # Received: 3.333333 + 1.5 = 4.833333 bags
        # Balance: 15 - 4.833333 = 10.166667 bags
        self.so1.refresh_from_db()
        self.so2.refresh_from_db()
        expected_payables = self.so1.total_rate + self.so2.total_rate

        # Check top-level aggregate counters (across all matching sizing records)
        self.assertEqual(D(res.data["totalBoxesSent"]), D("15"))
        self.assertEqual(D(res.data["totalBoxesReceived"]), D("4.833333"))
        self.assertEqual(D(res.data["totalBoxesBalance"]), D("10.166667"))
        self.assertEqual(D(res.data["totalPayables"]), expected_payables)

        # Check nested summary object has identical values
        summary = res.data["summary"]
        self.assertEqual(D(summary["totalBoxesSent"]), D("15"))
        self.assertEqual(D(summary["totalBoxesReceived"]), D("4.833333"))
        self.assertEqual(D(summary["totalBoxesBalance"]), D("10.166667"))
        self.assertEqual(D(summary["totalPayables"]), expected_payables)
        self.assertEqual(summary["totalSizingsCount"], 2)

        # Check per-sizing values on the rows
        by_name = {r["sizingName"]: r for r in results}
        alpha = by_name["Alpha Sizing"]
        self.assertEqual(D(alpha["totalBoxesSent"]), D("15"))
        self.assertEqual(D(alpha["totalBoxesReceived"]), D("4.833333"))
        self.assertEqual(D(alpha["totalBoxesBalance"]), D("10.166667"))
        self.assertEqual(D(alpha["totalPayables"]), expected_payables)
        self.assertEqual(alpha["transactionsCount"], 4)
        self.assertEqual(alpha["status"], "Active")

        beta = by_name["Beta Sizing"]
        self.assertEqual(D(beta["totalBoxesSent"]), D("0"))
        self.assertEqual(D(beta["totalBoxesReceived"]), D("0"))
        self.assertEqual(D(beta["totalBoxesBalance"]), D("0"))
        self.assertEqual(D(beta["totalPayables"]), D("0"))
        self.assertEqual(beta["transactionsCount"], 0)

    # ── 2. Individual Sizing Detail Ledger API ────────────────────────────

    def test_02_individual_sizing_ledger_via_retrieve_and_custom_action(self):
        """C: Detail ledger API for a selected sizing ID returns sizing details, counters, and transactions."""
        # Test 1: via GET /api/v1/sizing-ledger/{id}/
        res1 = self.client.get(f"{URL}{self.sizing_a.id}/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertTrue(res1.data["success"])

        # Test 2: via GET /api/v1/sizings/{id}/ledger/
        res2 = self.client.get(f"/api/v1/sizings/{self.sizing_a.id}/ledger/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        # Test 3: via GET /api/v1/sizing-ledger/?sizing={id}
        res3 = self.client.get(f"{URL}?sizing={self.sizing_a.id}")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)

        for res in (res1, res2, res3):
            data = res.data
            # Sizing details
            self.assertEqual(data["sizing"]["id"], self.sizing_a.id)
            self.assertEqual(data["sizing"]["sizingName"], "Alpha Sizing")
            self.assertEqual(data["sizing"]["contactPerson"], "Ali Khan")
            self.assertEqual(data["sizing"]["phoneNo"], "0300-1111111")
            self.assertEqual(data["sizing"]["status"], "Active")

            # Sizing counters
            expected_payables = self.so1.total_rate + self.so2.total_rate
            self.assertEqual(D(data["totalBoxesSent"]), D("15"))
            self.assertEqual(D(data["totalBoxesReceived"]), D("4.833333"))
            self.assertEqual(D(data["totalBoxesBalance"]), D("10.166667"))
            self.assertEqual(D(data["totalPayables"]), expected_payables)

            # Paginated transactions
            self.assertEqual(data["count"], 4)
            txs = data["results"]
            self.assertEqual(len(txs), 4)
            self.assertEqual(
                [t["id"] for t in txs],
                [f"IN-{self.yo1.id}", f"OUT-{self.so1.id}", f"IN-{self.yo2.id}", f"OUT-{self.so2.id}"],
            )
            # Both results and transactions keys present
            self.assertEqual(data["transactions"], txs)

    # ── 3. Calculations and running balance ────────────────────────────────

    def test_03_sent_received_and_running_balance_calculations(self):
        """D: Transaction running balances correctly maintain sent minus received."""
        res = self.client.get(f"{URL}{self.sizing_a.id}/")
        txs = res.data["results"]

        # Row 1 (IN 10): bal = 10
        self.assertEqual(D(txs[0]["bagsIn"]), D("10"))
        self.assertEqual(D(txs[0]["balanceBags"]), D("10"))
        self.assertIsNone(txs[0]["bagsOut"])

        # Row 2 (OUT 3.333333): bal = 10 - 3.333333 = 6.666667
        self.assertEqual(D(txs[1]["bagsOut"]), D("3.333333"))
        self.assertEqual(D(txs[1]["balanceBags"]), D("6.666667"))
        self.assertIsNone(txs[1]["bagsIn"])

        # Row 3 (IN 5): bal = 6.666667 + 5 = 11.666667
        self.assertEqual(D(txs[2]["bagsIn"]), D("5"))
        self.assertEqual(D(txs[2]["balanceBags"]), D("11.666667"))

        # Row 4 (OUT 1.5): bal = 11.666667 - 1.5 = 10.166667
        self.assertEqual(D(txs[3]["bagsOut"]), D("1.5"))
        self.assertEqual(D(txs[3]["balanceBags"]), D("10.166667"))

    # ── 4. Payable calculation ─────────────────────────────────────────────

    def test_04_payable_calculations_based_on_rate_and_net_weight(self):
        """D: Payable equals rate_per_kg * net_weight_kg (total_rate) and accumulates."""
        res = self.client.get(f"{URL}{self.sizing_a.id}/")
        txs = res.data["results"]

        charge1 = D("12.345678") * D("98.765432")
        charge2 = D("10") * D("50.5")

        self.assertEqual(D(txs[0]["chargesPayable"]), D("0"))
        self.assertEqual(D(txs[1]["sizingCharge"]), charge1)
        self.assertEqual(D(txs[1]["chargesPayable"]), charge1)
        self.assertEqual(D(txs[2]["chargesPayable"]), charge1)
        self.assertEqual(D(txs[3]["sizingCharge"]), charge2)
        self.assertEqual(D(txs[3]["chargesPayable"]), charge1 + charge2)

    # ── 5. Search, status, and date filters ─────────────────────────────────

    def test_05_main_sizing_ledger_filters(self):
        """B & F: Filtering by search and status on Main Sizing Ledger."""
        # Search by name
        res_search = self.client.get(URL, {"search": "alpha"})
        self.assertEqual(res_search.data["count"], 1)
        self.assertEqual(res_search.data["results"][0]["sizingName"], "Alpha Sizing")

        # Search nonexistent
        res_none = self.client.get(URL, {"search": "nonexistent"})
        self.assertEqual(res_none.data["count"], 0)
        self.assertEqual(res_none.data["results"], [])
        self.assertEqual(D(res_none.data["totalBoxesSent"]), D("0"))

        # Status filter
        res_status = self.client.get(URL, {"status": "Active"})
        self.assertEqual(res_status.data["count"], 2)

        res_inactive = self.client.get(URL, {"status": "Inactive"})
        self.assertEqual(res_inactive.data["count"], 0)

    def test_06_date_range_filtering_on_main_and_detail_ledgers(self):
        """B, C & F: Date range filters correctly restrict transactions and compute balances."""
        # Main ledger filtered from Oct 10
        res_main = self.client.get(URL, {"date_from": "2026-10-10"})
        # Only yo2 (5 bags) and so2 (1.5 bags) in range
        self.assertEqual(D(res_main.data["totalBoxesSent"]), D("5"))
        self.assertEqual(D(res_main.data["totalBoxesReceived"]), D("1.5"))
        self.assertEqual(D(res_main.data["totalBoxesBalance"]), D("3.5"))
        self.assertEqual(D(res_main.data["totalPayables"]), D("505"))

        # Detail ledger filtered from Oct 10
        res_detail = self.client.get(f"{URL}{self.sizing_a.id}/", {"date_from": "2026-10-10"})
        self.assertEqual(res_detail.data["count"], 2)
        self.assertEqual([t["id"] for t in res_detail.data["results"]], [f"IN-{self.yo2.id}", f"OUT-{self.so2.id}"])

        # Opening balance is balance prior to Oct 10 (Oct 5 balance: 10 - 3.333333 = 6.666667)
        opening = res_detail.data["openingBalance"]
        self.assertIsNotNone(opening)
        self.assertEqual(D(opening["balanceBags"]), D("6.666667"))

    # ── 6. Pagination covering all filtered records ────────────────────────

    def test_07_pagination_summaries_cover_all_records_not_just_current_page(self):
        """B & F: Aggregate counters reflect the entire filtered dataset across all pages."""
        # Create a third sizing
        Sizing.objects.create(sizing_name="Gamma Sizing", status="Active")

        res_p1 = self.client.get(URL, {"page": 1, "page_size": 1})
        self.assertEqual(res_p1.data["count"], 3)
        self.assertEqual(res_p1.data["totalPages"], 3)
        self.assertEqual(len(res_p1.data["results"]), 1)

        # Aggregate totalBoxesSent must still be 15 across the entire dataset!
        self.assertEqual(D(res_p1.data["totalBoxesSent"]), D("15"))
        self.assertEqual(D(res_p1.data["totalBoxesReceived"]), D("4.833333"))
        self.assertEqual(D(res_p1.data["totalBoxesBalance"]), D("10.166667"))

    # ── 7. Empty ledgers ───────────────────────────────────────────────────

    def test_08_empty_ledger_handling(self):
        """F: Sizing with zero transactions returns clean zero balances without errors."""
        res = self.client.get(f"{URL}{self.sizing_b.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["results"], [])
        self.assertEqual(D(res.data["totalBoxesSent"]), D("0"))
        self.assertEqual(D(res.data["totalBoxesReceived"]), D("0"))
        self.assertEqual(D(res.data["totalBoxesBalance"]), D("0"))
        self.assertEqual(D(res.data["totalPayables"]), D("0"))

    # ── 8. Duplicate joins verification ───────────────────────────────────

    def test_09_no_duplicate_totals_from_multiple_outcomes_or_joins(self):
        """F: Multiple SizingOutcomes under one YarnOutcome do not multiply sent boxes."""
        sizing_multi = Sizing.objects.create(sizing_name="Multi Sizing", status="Active")
        # Send 20 bags
        yo_multi = self._yarn_out(sizing_multi, bags=20, date="2026-10-15")

        # 3 separate SizingOutcomes linked to this single YarnOutcome
        self._sizing_out(yo_multi, date="2026-10-16", lagat_bags="5", lagat_cones="120", rate="10", net="100")
        self._sizing_out(yo_multi, date="2026-10-17", lagat_bags="5", lagat_cones="120", rate="10", net="100")
        self._sizing_out(yo_multi, date="2026-10-18", lagat_bags="5", lagat_cones="120", rate="10", net="100")

        res = self.client.get(f"{URL}{sizing_multi.id}/")
        # Sent must remain 20, NOT 20 * 3 = 60!
        self.assertEqual(D(res.data["totalBoxesSent"]), D("20"))
        self.assertEqual(D(res.data["totalBoxesReceived"]), D("15"))
        self.assertEqual(D(res.data["totalBoxesBalance"]), D("5"))
        self.assertEqual(D(res.data["totalPayables"]), D("3000"))

        # Verify on Main Sizing Ledger as well
        res_main = self.client.get(URL, {"search": "Multi Sizing"})
        multi_row = res_main.data["results"][0]
        self.assertEqual(D(multi_row["totalBoxesSent"]), D("20"))
        self.assertEqual(D(multi_row["totalBoxesReceived"]), D("15"))
        self.assertEqual(D(multi_row["totalBoxesBalance"]), D("5"))
        self.assertEqual(D(multi_row["totalPayables"]), D("3000"))

    # ── 9. Decimal precision ──────────────────────────────────────────────

    def test_10_decimal_precision_preserved_without_quantization(self):
        """F: Derived calculations retain full precision strings without float drift or rounding."""
        res = self.client.get(f"{URL}{self.sizing_a.id}/")
        txs = res.data["results"]

        out1 = txs[1]
        self.assertIsInstance(out1["weightKgOut"], str)
        # 3.333333 * 45.123457 has 12 decimal places
        val_d = D(out1["weightKgOut"])
        self.assertEqual(val_d.as_tuple().exponent, -12)
        self.assertEqual(val_d, D("3.333333") * D("45.123457"))

        # Product of rate_per_kg (12.345678) and net_weight_kg (98.765432) has 12 decimal places
        charge_d = D(out1["sizingCharge"])
        self.assertEqual(charge_d.as_tuple().exponent, -12)
        self.assertEqual(charge_d, D("12.345678") * D("98.765432"))

    # ── 10. Permissions and invalid sizing IDs ────────────────────────────

    def test_11_permissions_and_invalid_sizing_ids(self):
        """F: Proper RBAC permission enforcement and validation of sizing IDs."""
        # 1. Invalid sizing ID (non-integer)
        res_bad = self.client.get(f"{URL}abc/")
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)

        res_bad_param = self.client.get(URL, {"sizing": "abc"})
        self.assertEqual(res_bad_param.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Nonexistent sizing ID
        res_404 = self.client.get(f"{URL}999999/")
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

        res_404_action = self.client.get("/api/v1/sizings/999999/ledger/")
        self.assertEqual(res_404_action.status_code, status.HTTP_404_NOT_FOUND)

        # Nonexistent sizing ID in query param returns empty
        res_empty = self.client.get(URL, {"sizing": 999999})
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(res_empty.data["count"], 0)

        # 3. RBAC permissions
        viewer_role = Role.objects.create(
            name="Ledger Viewer", slug="ledger-viewer", status="Active", permissions=["sizing.view"]
        )
        viewer = User.objects.create_user(
            username="ledger_viewer", email="lv@example.com", password="pw-12345-abc",
            role=viewer_role, status="Active",
        )
        other_role = Role.objects.create(
            name="Beam Only", slug="beam-only", status="Active", permissions=["beams.view"]
        )
        other = User.objects.create_user(
            username="ledger_other", email="lo@example.com", password="pw-12345-abc",
            role=other_role, status="Active",
        )

        self.client.force_authenticate(user=viewer)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f"{URL}{self.sizing_a.id}/").status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=other)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(f"{URL}{self.sizing_a.id}/").status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=None)
        self.assertIn(
            self.client.get(URL).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    # ── 11. Transactions stream and CSV export ────────────────────────────

    def test_12_transactions_stream_and_csv_export(self):
        """F: Transactions stream endpoint and CSV export functionality."""
        # Transactions stream
        res_tx = self.client.get(f"{URL}transactions/", {"sizing": self.sizing_a.id})
        self.assertEqual(res_tx.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_tx.data["results"]), 4)

        # CSV export (Main Sizing Ledger)
        res_csv_main = self.client.get(f"{URL}export/")
        self.assertEqual(res_csv_main.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", res_csv_main["Content-Type"])
        reader_main = list(csv.DictReader(io.StringIO(res_csv_main.content.decode("utf-8"))))
        self.assertEqual(len(reader_main), 2)
        self.assertIn("Total Boxes Sent", reader_main[0])

        # CSV export (Transactions)
        res_csv_tx = self.client.get(f"{URL}export/", {"sizing": self.sizing_a.id, "mode": "transactions"})
        self.assertEqual(res_csv_tx.status_code, status.HTTP_200_OK)
        reader_tx = list(csv.DictReader(io.StringIO(res_csv_tx.content.decode("utf-8"))))
        self.assertEqual(len(reader_tx), 4)
        self.assertEqual(reader_tx[0]["Type"], "income")
