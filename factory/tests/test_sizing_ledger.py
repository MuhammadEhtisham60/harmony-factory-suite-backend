"""
Tests for the read-only Sizing Ledger API (/api/v1/sizing-ledger/).

Covers:
- income (YarnOutcome -> Sizing) and outcome (SizingOutcome) rows
- chronological ordering and per-sizing running balances
- exact fractional precision across chained balances (no rounding / quantization)
- date / type / set / search filters keep TRUE cumulative balances + openingBalance
- pagination carries balances across pages
- independent balances per sizing party
- updates and deletions are reflected immediately
- summary and CSV export agree with the list endpoint
- permissions and parameter validation
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
    # Fractional inputs chosen so products have MORE than 6 decimals (12 dp),
    # which proves nothing is quantized on the way out.
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

        self.sizing_a = Sizing.objects.create(sizing_name="Alpha Sizing", status="Active")
        self.sizing_b = Sizing.objects.create(sizing_name="Beta Sizing", status="Active")

        # ── Sizing A: IN, OUT, IN, OUT ────────────────────────────────────
        self.yo1 = self._yarn_out(self.sizing_a, bags=10, date="2026-10-02")
        self.so1 = self._sizing_out(
            self.yo1, date="2026-10-05", lagat_bags="3.333333", lagat_cones="80.000001",
            rate="12.345678", net="98.765432", set_no="SET-1", set_bill="B-1",
        )
        self.yo2 = self._yarn_out(self.sizing_a, bags=5, date="2026-10-10")
        self.so2 = self._sizing_out(
            self.yo2, date="2026-10-12", lagat_bags="1.5", lagat_cones="36",
            rate="10", net="50.5", set_no="SET-2", set_bill="B-2",
        )

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

    def _get(self, **params):
        res = self.client.get(URL, params)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        return res

    # ── expected values (computed independently with plain Decimal) ───────

    def _expected_sizing_a(self):
        w = self.WEIGHT_PER_BAG
        in1_kg = D(10) * w
        out1_kg = D("3.333333") * w
        in2_kg = D(5) * w
        out2_kg = D("1.5") * w
        charge1 = D("12.345678") * D("98.765432")
        charge2 = D("10") * D("50.5")

        kg_after = [
            in1_kg,
            in1_kg - out1_kg,
            in1_kg - out1_kg + in2_kg,
            in1_kg - out1_kg + in2_kg - out2_kg,
        ]
        bags_after = [D(10), D(10) - D("3.333333"), D(15) - D("3.333333"), D(15) - D("3.333333") - D("1.5")]
        cones_after = [
            D(240),
            D(240) - D("80.000001"),
            D(360) - D("80.000001"),
            D(360) - D("80.000001") - D(36),
        ]
        charges_after = [D(0), charge1, charge1, charge1 + charge2]
        return {
            "in1_kg": in1_kg, "out1_kg": out1_kg, "in2_kg": in2_kg, "out2_kg": out2_kg,
            "charge1": charge1, "charge2": charge2,
            "kg_after": kg_after, "bags_after": bags_after,
            "cones_after": cones_after, "charges_after": charges_after,
        }

    # ── 1. rows, ordering, exact balances ─────────────────────────────────

    def test_01_rows_ordering_and_exact_running_balances(self):
        res = self._get(sizing=self.sizing_a.id, page_size=100)
        rows = res.data["results"]
        self.assertEqual(
            [r["id"] for r in rows],
            [f"IN-{self.yo1.id}", f"OUT-{self.so1.id}", f"IN-{self.yo2.id}", f"OUT-{self.so2.id}"],
        )
        self.assertEqual([r["entryType"] for r in rows], ["income", "outcome", "income", "outcome"])

        e = self._expected_sizing_a()
        for i, row in enumerate(rows):
            self.assertEqual(D(row["balanceWeightKg"]), e["kg_after"][i])
            self.assertEqual(D(row["balanceBags"]), e["bags_after"][i])
            self.assertEqual(D(row["balanceCones"]), e["cones_after"][i])
            self.assertEqual(D(row["chargesPayable"]), e["charges_after"][i])
            self.assertEqual(D(row["balanceWeightLb"]), e["kg_after"][i] * LB_PER_KG)

        # income row columns
        self.assertEqual(D(rows[0]["bagsIn"]), D(10))
        self.assertEqual(D(rows[0]["conesIn"]), D(240))
        self.assertEqual(D(rows[0]["weightKgIn"]), e["in1_kg"])
        self.assertEqual(D(rows[0]["weightLbIn"]), e["in1_kg"] * LB_PER_KG)
        self.assertIsNone(rows[0]["bagsOut"])
        self.assertIsNone(rows[0]["sizingOutcomeId"])
        self.assertEqual(rows[0]["yarnOutcomeId"], self.yo1.id)

        # outcome row columns
        self.assertEqual(D(rows[1]["bagsOut"]), D("3.333333"))
        self.assertEqual(D(rows[1]["conesOut"]), D("80.000001"))
        self.assertEqual(D(rows[1]["weightKgOut"]), e["out1_kg"])
        self.assertEqual(D(rows[1]["sizingCharge"]), e["charge1"])
        self.assertEqual(D(rows[1]["ratePerKg"]), D("12.345678"))
        self.assertEqual(D(rows[1]["netWeightKg"]), D("98.765432"))
        self.assertIsNone(rows[1]["bagsIn"])
        self.assertEqual(rows[1]["reference"], "Set #SET-1 / Bill #B-1")
        self.assertEqual(rows[1]["setNo"], "SET-1")
        self.assertEqual(rows[1]["sizingOutcomeId"], self.so1.id)

    def test_02_values_are_exact_strings_not_quantized_to_6_decimals(self):
        rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        e = self._expected_sizing_a()

        out1 = rows[1]
        self.assertIsInstance(out1["weightKgOut"], str)
        # 3.333333 * 45.123457 has 12 decimal places; a 6dp DecimalField would have rounded it.
        self.assertEqual(D(out1["weightKgOut"]).as_tuple().exponent, -12)
        self.assertEqual(D(out1["weightKgOut"]), D("3.333333") * D("45.123457"))
        self.assertNotEqual(D(out1["weightKgOut"]), e["out1_kg"].quantize(D("0.000001")))

        # product of two 6dp values -> 12dp charge, kept intact
        self.assertEqual(D(out1["sizingCharge"]).as_tuple().exponent, -12)
        self.assertEqual(D(out1["sizingCharge"]), D("12.345678") * D("98.765432"))

        # no scientific notation / floats anywhere
        for row in rows:
            for key in ("balanceBags", "balanceCones", "balanceWeightKg", "balanceWeightLb", "chargesPayable"):
                self.assertIsInstance(row[key], str)
                self.assertNotIn("E", row[key].upper())

    # ── 2. filters ────────────────────────────────────────────────────────

    def test_03_entry_type_filter(self):
        inc = self._get(sizing=self.sizing_a.id, entry_type="income", page_size=100).data["results"]
        out = self._get(sizing=self.sizing_a.id, entry_type="outcome", page_size=100).data["results"]
        self.assertEqual({r["entryType"] for r in inc}, {"income"})
        self.assertEqual({r["entryType"] for r in out}, {"outcome"})
        self.assertEqual(len(inc), 2)
        self.assertEqual(len(out), 2)

        # filtering by type does not restart the balance
        e = self._expected_sizing_a()
        self.assertEqual(D(out[0]["balanceWeightKg"]), e["kg_after"][1])
        self.assertEqual(D(out[1]["balanceWeightKg"]), e["kg_after"][3])

    def test_04_date_filter_keeps_true_cumulative_balance_and_opening_balance(self):
        res = self._get(sizing=self.sizing_a.id, date_from="2026-10-10", page_size=100)
        rows = res.data["results"]
        self.assertEqual([r["id"] for r in rows], [f"IN-{self.yo2.id}", f"OUT-{self.so2.id}"])

        e = self._expected_sizing_a()
        # first visible row continues from the earlier history
        self.assertEqual(D(rows[0]["balanceWeightKg"]), e["kg_after"][2])
        self.assertEqual(D(rows[1]["balanceWeightKg"]), e["kg_after"][3])

        opening = res.data["openingBalance"]
        self.assertEqual(D(opening["balanceWeightKg"]), e["kg_after"][1])
        self.assertEqual(D(opening["balanceBags"]), e["bags_after"][1])
        self.assertEqual(D(opening["balanceCones"]), e["cones_after"][1])
        self.assertEqual(D(opening["chargesPayable"]), e["charges_after"][1])
        self.assertEqual(D(opening["balanceWeightLb"]), e["kg_after"][1] * LB_PER_KG)

    def test_05_opening_balance_zero_without_date_from_and_none_without_sizing(self):
        res = self._get(sizing=self.sizing_a.id)
        self.assertEqual(D(res.data["openingBalance"]["balanceWeightKg"]), D(0))
        res_all = self._get()
        self.assertIsNone(res_all.data["openingBalance"])

    def test_06_date_to_filter(self):
        rows = self._get(sizing=self.sizing_a.id, date_to="2026-10-05", page_size=100).data["results"]
        self.assertEqual([r["id"] for r in rows], [f"IN-{self.yo1.id}", f"OUT-{self.so1.id}"])

    def test_07_search_and_set_no_filters(self):
        rows = self._get(sizing=self.sizing_a.id, set_no="set-2", page_size=100).data["results"]
        self.assertEqual([r["id"] for r in rows], [f"OUT-{self.so2.id}"])

        rows = self._get(search="B-1", page_size=100).data["results"]
        self.assertEqual([r["id"] for r in rows], [f"OUT-{self.so1.id}"])

        rows = self._get(search="alpha", page_size=100).data["results"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(self._get(search="no-such-text").data["count"], 0)

    def test_08_descending_order_keeps_same_balances(self):
        asc = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        desc = self._get(sizing=self.sizing_a.id, ordering="-date", page_size=100).data["results"]
        self.assertEqual([r["id"] for r in desc], [r["id"] for r in reversed(asc)])
        self.assertEqual(
            [r["balanceWeightKg"] for r in desc], [r["balanceWeightKg"] for r in reversed(asc)]
        )

    # ── 3. pagination ─────────────────────────────────────────────────────

    def test_09_pagination_carries_balances_across_pages(self):
        e = self._expected_sizing_a()
        p1 = self._get(sizing=self.sizing_a.id, page_size=2, page=1)
        p2 = self._get(sizing=self.sizing_a.id, page_size=2, page=2)
        self.assertEqual(p1.data["count"], 4)
        self.assertEqual(p1.data["totalPages"], 2)
        self.assertEqual(D(p1.data["results"][1]["balanceWeightKg"]), e["kg_after"][1])
        self.assertEqual(D(p2.data["results"][0]["balanceWeightKg"]), e["kg_after"][2])
        self.assertEqual(D(p2.data["results"][1]["balanceWeightKg"]), e["kg_after"][3])

    # ── 4. multiple parties ───────────────────────────────────────────────

    def test_10_each_sizing_party_has_independent_balances(self):
        yo_b = self._yarn_out(self.sizing_b, bags=7, date="2026-10-03", per_bag=D("40.000001"))
        so_b = self._sizing_out(
            yo_b, date="2026-10-04", lagat_bags="2.000001", lagat_cones="10", rate="5", net="20",
            set_no="SET-B", set_bill="BB-1",
        )
        rows = self._get(page_size=100).data["results"]
        self.assertEqual(len(rows), 6)

        by_id = {r["id"]: r for r in rows}
        in_b = by_id[f"IN-{yo_b.id}"]
        out_b = by_id[f"OUT-{so_b.id}"]
        self.assertEqual(D(in_b["balanceWeightKg"]), D(7) * D("40.000001"))
        self.assertEqual(D(out_b["balanceWeightKg"]), D(7) * D("40.000001") - D("2.000001") * D("40.000001"))
        self.assertEqual(D(out_b["chargesPayable"]), D("5") * D("20"))

        # Sizing A rows are not affected by Sizing B activity
        e = self._expected_sizing_a()
        self.assertEqual(D(by_id[f"OUT-{self.so2.id}"]["balanceWeightKg"]), e["kg_after"][3])

        only_b = self._get(sizing=self.sizing_b.id, page_size=100).data["results"]
        self.assertEqual({r["sizingId"] for r in only_b}, {self.sizing_b.id})

    def test_11_same_date_income_is_listed_before_outcome(self):
        yo = self._yarn_out(self.sizing_b, bags=2, date="2026-10-20")
        so = self._sizing_out(yo, date="2026-10-20", lagat_bags="1", lagat_cones="1", rate="1", net="1")
        # make the income row the NEWER record; same date -> income must still sort first
        YarnOutcome.objects.filter(id=yo.id).update(created_at=so.created_at + timedelta(seconds=30))
        rows = self._get(sizing=self.sizing_b.id).data["results"]
        self.assertEqual([r["id"] for r in rows], [f"IN-{yo.id}", f"OUT-{so.id}"])
        self.assertEqual(D(rows[1]["balanceBags"]), D(1))

    # ── 5. updates and deletions ──────────────────────────────────────────

    def test_12_updates_are_reflected_without_precision_loss(self):
        self.so1.lagat_bags = D("0.000001")
        self.so1.rate_per_kg = D("0.000001")
        self.so1.net_weight_kg = D("0.000001")
        self.so1.save()

        rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        out1 = rows[1]
        self.assertEqual(D(out1["bagsOut"]), D("0.000001"))
        self.assertEqual(D(out1["weightKgOut"]), D("0.000001") * D("45.123457"))
        self.assertEqual(D(out1["sizingCharge"]), D("0.000001") * D("0.000001"))
        self.assertEqual(D(out1["sizingCharge"]).as_tuple().exponent, -12)

        w = self.WEIGHT_PER_BAG
        self.assertEqual(D(out1["balanceWeightKg"]), D(10) * w - D("0.000001") * w)

        # yarn-outcome edit flows into income and the outcome's consumed kg
        self.yo1.outcome_weight_per_bag_kg = D("1.000001")
        self.yo1.save()
        rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        self.assertEqual(D(rows[0]["weightKgIn"]), D(10) * D("1.000001"))
        self.assertEqual(D(rows[1]["weightKgOut"]), D("0.000001") * D("1.000001"))

    def test_13_deletions_are_reflected_and_balances_recomputed(self):
        self.so2.delete()
        rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        self.assertEqual(
            [r["id"] for r in rows],
            [f"IN-{self.yo1.id}", f"OUT-{self.so1.id}", f"IN-{self.yo2.id}"],
        )
        e = self._expected_sizing_a()
        self.assertEqual(D(rows[-1]["balanceWeightKg"]), e["kg_after"][2])
        self.assertEqual(D(rows[-1]["chargesPayable"]), e["charge1"])

        self.yo2.delete()
        rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        self.assertEqual([r["id"] for r in rows], [f"IN-{self.yo1.id}", f"OUT-{self.so1.id}"])
        self.assertEqual(D(rows[-1]["balanceWeightKg"]), e["kg_after"][1])

    def test_14_non_sizing_yarn_outcomes_are_not_in_ledger(self):
        YarnOutcome.objects.create(
            yarn_intake=self.intake,
            outcome_type=YarnOutcome.OutcomeTypeChoices.WEFT,
            outcome_bags=3,
            outcome_cones_per_bag=24,
            outcome_weight_per_bag_kg=D("45.36"),
            outcome_date="2026-10-06",
        )
        self.assertEqual(self._get(page_size=100).data["count"], 4)

    # ── 6. summary + export ───────────────────────────────────────────────

    def test_15_summary_totals_and_closing_balances(self):
        res = self.client.get(URL + "summary/", {"sizing": self.sizing_a.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data["data"]
        e = self._expected_sizing_a()
        t = data["totals"]

        self.assertEqual(t["entries"], 4)
        self.assertEqual(D(t["totalBagsIn"]), D(15))
        self.assertEqual(D(t["totalConesIn"]), D(360))
        self.assertEqual(D(t["totalWeightKgIn"]), e["in1_kg"] + e["in2_kg"])
        self.assertEqual(D(t["totalBagsOut"]), D("3.333333") + D("1.5"))
        self.assertEqual(D(t["totalConesOut"]), D("80.000001") + D(36))
        self.assertEqual(D(t["totalWeightKgOut"]), e["out1_kg"] + e["out2_kg"])
        self.assertEqual(D(t["totalSizingCharge"]), e["charge1"] + e["charge2"])
        self.assertEqual(D(t["balanceWeightKg"]), e["kg_after"][3])
        self.assertEqual(D(t["balanceBags"]), e["bags_after"][3])
        self.assertEqual(D(t["balanceCones"]), e["cones_after"][3])
        self.assertEqual(D(t["chargesPayable"]), e["charges_after"][3])

        self.assertEqual(len(data["parties"]), 1)
        self.assertEqual(data["parties"][0]["sizingId"], self.sizing_a.id)
        self.assertEqual(data["parties"][0]["sizingName"], "Alpha Sizing")
        self.assertEqual(D(data["parties"][0]["balanceWeightKg"]), e["kg_after"][3])

    def test_16_summary_across_parties_sums_party_closings(self):
        yo_b = self._yarn_out(self.sizing_b, bags=4, date="2026-10-03", per_bag=D("20.000001"))
        res = self.client.get(URL + "summary/")
        data = res.data["data"]
        self.assertEqual(len(data["parties"]), 2)
        e = self._expected_sizing_a()
        expected_total_kg = e["kg_after"][3] + D(4) * D("20.000001")
        self.assertEqual(D(data["totals"]["balanceWeightKg"]), expected_total_kg)
        self.assertEqual(yo_b.sizing_id, self.sizing_b.id)

    def test_17_csv_export_matches_api_values(self):
        api_rows = self._get(sizing=self.sizing_a.id, page_size=100).data["results"]
        res = self.client.get(URL + "export/", {"sizing": self.sizing_a.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", res["Content-Type"])

        reader = list(csv.DictReader(io.StringIO(res.content.decode("utf-8"))))
        self.assertEqual(len(reader), len(api_rows))
        for csv_row, api_row in zip(reader, api_rows):
            self.assertEqual(csv_row["Type"], api_row["entryType"])
            self.assertEqual(csv_row["Date"], api_row["date"])
            self.assertEqual(csv_row["Balance Weight (kg)"], api_row["balanceWeightKg"])
            self.assertEqual(csv_row["Balance Bags"], api_row["balanceBags"])
            self.assertEqual(csv_row["Charges Payable"], api_row["chargesPayable"])
        self.assertEqual(reader[1]["Weight Out (kg)"], api_rows[1]["weightKgOut"])
        self.assertEqual(reader[1]["Sizing Charge"], api_rows[1]["sizingCharge"])
        self.assertEqual(reader[0]["Weight Out (kg)"], "")

    # ── 7. permissions + validation ───────────────────────────────────────

    def test_18_permissions(self):
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
        for path in (URL, URL + "summary/", URL + "export/"):
            self.assertEqual(self.client.get(path).status_code, status.HTTP_200_OK, path)

        self.client.force_authenticate(user=other)
        for path in (URL, URL + "summary/", URL + "export/"):
            self.assertEqual(self.client.get(path).status_code, status.HTTP_403_FORBIDDEN, path)

        self.client.force_authenticate(user=None)
        self.assertIn(
            self.client.get(URL).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        # read-only: no write verbs
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_19_invalid_parameters_return_400(self):
        for params in (
            {"sizing": "abc"},
            {"date_from": "10/10/2026"},
            {"date_to": "not-a-date"},
            {"entry_type": "bogus"},
            {"ordering": "name"},
            {"date_from": "2026-10-12", "date_to": "2026-10-01"},
        ):
            res = self.client.get(URL, params)
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, params)

    def test_20_empty_ledger_for_unknown_sizing(self):
        res = self._get(sizing=999999)
        self.assertEqual(res.data["count"], 0)
        self.assertEqual(res.data["results"], [])
        summary = self.client.get(URL + "summary/", {"sizing": 999999}).data["data"]
        self.assertEqual(summary["totals"]["entries"], 0)
        self.assertEqual(D(summary["totals"]["balanceWeightKg"]), D(0))
