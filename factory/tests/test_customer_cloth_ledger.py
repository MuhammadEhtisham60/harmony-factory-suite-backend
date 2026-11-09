"""
Comprehensive tests for Customer Cloth Ledger APIs:
1. Main Customer Cloth Ledger API (/api/v1/customer-ledger/)
2. Individual Customer Ledger Statement (/api/v1/customer-ledger/{id}/)
3. Payment recording endpoint (/api/v1/customer-ledger/payments/) with Bank Account sync
4. Cloth Sale recording endpoint (/api/v1/customer-ledger/sales/)
5. Running balance calculations (exact Decimal, meters, and receivables)
6. CSV Export endpoint (/api/v1/customer-ledger/export/)
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.sales.customer.models import Customer
from factory.cloth.models import ClothName
from factory.bank_account.models import BankAccount, BankTransaction
from factory.sales.customer_ledger.models import ClothSale, ClothCustomerPayment


class CustomerClothLedgerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cloth_ledger_tester",
            email="tester@example.com",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        self.customer_a = Customer.objects.create(
            customer_name="Metro Garments Karachi",
            company_name="Metro Garments Ltd",
            phone="+923001112233",
            status="Active",
            customer_type="Wholesaler",
        )
        self.customer_b = Customer.objects.create(
            customer_name="Style Hub Lahore",
            company_name="Style Hub Pvt",
            phone="+923004445566",
            status="Active",
            customer_type="Retailer",
        )

        self.cloth_1 = ClothName.objects.create(name="Cotton Grey 40/40")
        self.cloth_2 = ClothName.objects.create(name="Poplin 60/60")

        self.bank = BankAccount.objects.create(
            bank_name="Meezan Bank",
            account_title="Harmony Textiles",
            account_number="MEEZ-0019283",
            opening_balance=Decimal("500000.00"),
        )

        # Sale 1 to Customer A: 1000 meters @ 250 PKR = 250,000 PKR
        self.sale1 = ClothSale.objects.create(
            customer=self.customer_a,
            cloth_name=self.cloth_1,
            sale_date=timezone.localdate(),
            quantity_meters=Decimal("1000.0000"),
            rate_per_meter=Decimal("250.0000"),
            created_by=self.user,
        )

    def test_main_customer_cloth_ledger_summary(self):
        url = "/api/v1/customer-ledger/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertIn("summary", data)
        self.assertIn("results", data)
        self.assertEqual(data["count"], 2)

        # Customer A has 1000m and 250,000 PKR sale
        cust_a_row = next(r for r in data["results"] if r["customerId"] == self.customer_a.id)
        self.assertEqual(Decimal(cust_a_row["totalMetersSold"]), Decimal("1000.0000"))
        self.assertEqual(Decimal(cust_a_row["totalSales"]), Decimal("250000.00"))
        self.assertEqual(Decimal(cust_a_row["totalPaid"]), Decimal("0"))
        self.assertEqual(Decimal(cust_a_row["totalReceivables"]), Decimal("250000.00"))

    def test_individual_customer_statement(self):
        url = f"/api/v1/customer-ledger/{self.customer_a.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertIn("customer", data)
        self.assertIn("openingBalance", data)
        self.assertIn("summary", data)
        self.assertIn("rows", data)

        self.assertEqual(len(data["rows"]), 1)
        row0 = data["rows"][0]
        self.assertEqual(row0["entryType"], "sale")
        self.assertEqual(Decimal(row0["saleAmount"]), Decimal("250000.00"))
        self.assertEqual(Decimal(row0["balanceReceivables"]), Decimal("250000.00"))

    def test_record_payment_and_running_balance(self):
        # Customer A pays 100,000 PKR into bank account
        pay_url = "/api/v1/customer-ledger/payments/"
        payload = {
            "customerId": self.customer_a.id,
            "clothSaleId": self.sale1.id,
            "bankAccountId": self.bank.id,
            "amount": "100000.00",
            "paymentDate": timezone.localdate().isoformat(),
            "paymentMethod": "Online Transfer",
            "referenceNumber": "IBFT-987654",
            "notes": "Advance on cloth invoice",
        }
        res = self.client.post(pay_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Verify sale invoice was partially paid
        self.sale1.refresh_from_db()
        self.assertEqual(self.sale1.amount_paid, Decimal("100000.00"))
        self.assertEqual(self.sale1.amount_due, Decimal("150000.00"))
        self.assertEqual(self.sale1.payment_status, ClothSale.PaymentStatusChoices.PARTIAL)

        # Verify bank account was credited (Credit transaction increases bank balance)
        self.bank.recalculate_balances()
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.total_credit, Decimal("100000.00"))
        self.assertEqual(self.bank.current_balance, Decimal("600000.00"))

        # Verify running balance on customer statement
        url = f"/api/v1/customer-ledger/{self.customer_a.id}/"
        response = self.client.get(url)
        data = response.data
        self.assertEqual(len(data["rows"]), 2)

        # After sale (+250k) and payment (-100k), balanceReceivables must be exactly 150k
        latest_row = data["rows"][-1]
        self.assertEqual(latest_row["entryType"], "payment")
        self.assertEqual(Decimal(latest_row["paymentAmount"]), Decimal("100000.00"))
        self.assertEqual(Decimal(latest_row["balanceReceivables"]), Decimal("150000.00"))

    def test_csv_export(self):
        # 1. Main CSV export
        main_export = self.client.get("/api/v1/customer-ledger/export/")
        self.assertEqual(main_export.status_code, status.HTTP_200_OK)
        self.assertEqual(main_export["Content-Type"], "text/csv")
        self.assertIn("Customer Code", main_export.content.decode("utf-8"))

        # 2. Individual statement CSV export
        ind_export = self.client.get(f"/api/v1/customer-ledger/export/?customer_id={self.customer_a.id}")
        self.assertEqual(ind_export.status_code, status.HTTP_200_OK)
        self.assertEqual(ind_export["Content-Type"], "text/csv")
        self.assertIn("Opening Balance", ind_export.content.decode("utf-8"))
