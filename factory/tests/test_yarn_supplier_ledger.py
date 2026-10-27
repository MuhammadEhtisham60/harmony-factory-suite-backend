"""
Comprehensive tests for Yarn Supplier Ledger APIs:
1. Main Yarn Supplier Ledger API (/api/v1/yarn-supplier-ledger/)
2. Individual Supplier Ledger API (/api/v1/yarn-supplier-ledger/{id}/)
3. Payment recording endpoint (/api/v1/yarn-supplier-ledger/payments/)
4. Running balance calculations (exact Decimal, bags, weight, and payables)
5. CSV Export endpoint (/api/v1/yarn-supplier-ledger/export/)
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_intake.models import YarnIntake
from factory.bank_account.models import BankAccount
from factory.yarn.supplier_ledger.models import YarnSupplierPayment


class YarnSupplierLedgerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ledger_tester",
            email="tester@example.com",
            password="password123",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

        self.supplier_a = Supplier.objects.create(
            supplier_name="National Spinning Mills",
            company_name="National Mills Ltd",
            phone="+923001234567",
            status="Active",
            supplier_type="Yarn",
        )
        self.supplier_b = Supplier.objects.create(
            supplier_name="Al-Karam Yarn",
            company_name="Al-Karam Textiles",
            phone="+923007654321",
            status="Active",
            supplier_type="Yarn",
        )

        self.y_name = YarnName.objects.create(name="Cotton Carded")
        self.y_type = YarnType.objects.create(name="Carded")
        self.y_count = YarnCount.objects.create(name="30/1")

        # Create intake 1 for Supplier A: 10 bags, 45.36 kg/bag, rate 100/lb
        # 10 bags * 45.36 kg = 453.6 kg * 2.20462262 = 1000.016820 lb * 100 = 100001.682047
        self.intake1 = YarnIntake.objects.create(
            supplier=self.supplier_a,
            yarn_name=self.y_name,
            yarn_type=self.y_type,
            yarn_count=self.y_count,
            bags=10,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_lb=Decimal("100.000000"),
            intake_date=timezone.now().date(),
            set_no="BATCH-A01",
            production_type="Self",
        )

        # Create intake 2 for Supplier A: 5 bags
        self.intake2 = YarnIntake.objects.create(
            supplier=self.supplier_a,
            yarn_name=self.y_name,
            yarn_type=self.y_type,
            yarn_count=self.y_count,
            bags=5,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("45.36"),
            rate_per_lb=Decimal("120.000000"),
            intake_date=timezone.now().date(),
            set_no="BATCH-A02",
            production_type="Self",
        )

        # Create intake for Supplier B: 20 bags
        self.intake_b = YarnIntake.objects.create(
            supplier=self.supplier_b,
            yarn_name=self.y_name,
            yarn_type=self.y_type,
            yarn_count=self.y_count,
            bags=20,
            cones_per_bag=24,
            weight_per_bag_kg=Decimal("50.00"),
            rate_per_lb=Decimal("150.000000"),
            intake_date=timezone.now().date(),
            set_no="BATCH-B01",
            production_type="Self",
        )

    def test_01_main_yarn_supplier_ledger_list(self):
        """GET /api/v1/yarn-supplier-ledger/ returns all suppliers with accurate totals and payables."""
        url = "/api/v1/yarn-supplier-ledger/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 2)

        # Verify Supplier A totals
        sup_a_row = next(r for r in data["results"] if r["id"] == self.supplier_a.id)
        self.assertEqual(Decimal(sup_a_row["totalBagsReceived"]), Decimal("15"))
        self.assertGreater(Decimal(sup_a_row["totalPurchases"]), Decimal("0"))
        self.assertEqual(Decimal(sup_a_row["totalPaid"]), Decimal("0"))
        self.assertEqual(Decimal(sup_a_row["totalPayables"]), Decimal(sup_a_row["totalPurchases"]))

    def test_02_individual_supplier_ledger(self):
        """GET /api/v1/yarn-supplier-ledger/{id}/ returns chronological intake transactions with running balances."""
        url = f"/api/v1/yarn-supplier-ledger/{self.supplier_a.id}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertTrue(data["success"])
        self.assertEqual(data["supplier"]["id"], self.supplier_a.id)
        self.assertEqual(data["count"], 2)

        txs = data["results"]
        # Check first intake row
        r1 = txs[0]
        self.assertEqual(r1["entryType"], "intake")
        self.assertEqual(Decimal(r1["bagsIn"]), Decimal("10"))
        self.assertEqual(Decimal(r1["balanceBags"]), Decimal("10"))

        # Check second intake row
        r2 = txs[1]
        self.assertEqual(Decimal(r2["bagsIn"]), Decimal("5"))
        self.assertEqual(Decimal(r2["balanceBags"]), Decimal("15"))
        self.assertGreater(Decimal(r2["balancePayables"]), Decimal(r1["balancePayables"]))

    def test_03_record_supplier_payment_updates_ledger_and_payables(self):
        """POST /api/v1/yarn-supplier-ledger/payments/ records payment and reduces outstanding payables."""
        self.bank = BankAccount.objects.create(
            bank_name="Meezan Bank",
            account_title="Factory Operations",
            account_number="PK1234567890",
            opening_balance=Decimal("500000.00"),
            current_balance=Decimal("500000.00"),
        )

        pay_url = "/api/v1/yarn-supplier-ledger/payments/"
        payment_amount = Decimal("25000.00")
        payload = {
            "supplierId": self.supplier_a.id,
            "yarnIntakeId": self.intake1.id,
            "bankAccountId": self.bank.id,
            "amount": str(payment_amount),
            "paymentDate": timezone.now().date().isoformat(),
            "paymentMethod": "Online Transfer",
            "referenceNumber": "IBFT-987654",
            "notes": "Partial payment towards BATCH-A01",
        }
        res_pay = self.client.post(pay_url, payload, format="json")
        self.assertEqual(res_pay.status_code, status.HTTP_201_CREATED)

        # Check intake1 payment status updated
        self.intake1.refresh_from_db()
        self.assertEqual(Decimal(str(self.intake1.amount_paid)), payment_amount)
        self.assertEqual(self.intake1.payment_status, "Partially Paid")

        # Check bank account balance deducted immediately
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.current_balance, Decimal("500000.00") - payment_amount)
        self.assertEqual(self.bank.total_debit, payment_amount)
        self.assertTrue(
            self.bank.transactions.filter(
                transaction_type="Debit",
                amount=payment_amount,
                reference_number="IBFT-987654"
            ).exists()
        )

        # Check individual ledger now has 3 transactions (2 intakes + 1 payment)
        ledger_url = f"/api/v1/yarn-supplier-ledger/{self.supplier_a.id}/"
        res_led = self.client.get(ledger_url)
        self.assertEqual(res_led.data["count"], 3)

        # Check closing payables reduced by payment_amount
        summary = res_led.data["summary"]
        expected_payables = Decimal(summary["totalPurchases"]) - payment_amount
        self.assertEqual(Decimal(summary["totalPaid"]), payment_amount)
        self.assertEqual(Decimal(summary["totalPayables"]), expected_payables)

    def test_04_csv_export_endpoints(self):
        """GET /api/v1/yarn-supplier-ledger/export/ returns CSV content for main summary and individual supplier."""
        # Export main summary
        res_main_csv = self.client.get("/api/v1/yarn-supplier-ledger/export/")
        self.assertEqual(res_main_csv.status_code, status.HTTP_200_OK)
        self.assertEqual(res_main_csv["Content-Type"], "text/csv")
        content_main = res_main_csv.content.decode("utf-8")
        self.assertIn("YARN SUPPLIERS LEDGER SUMMARY", content_main)
        self.assertIn("National Spinning Mills", content_main)

        # Export individual supplier statement
        res_ind_csv = self.client.get(f"/api/v1/yarn-supplier-ledger/export/?supplier={self.supplier_a.id}")
        self.assertEqual(res_ind_csv.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ind_csv["Content-Type"], "text/csv")
        content_ind = res_ind_csv.content.decode("utf-8")
        self.assertIn("YARN SUPPLIER LEDGER STATEMENT", content_ind)
        self.assertIn("BATCH-A01", content_ind)
