from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from factory.bank_account.models import BankAccount, BankTransaction

User = get_user_model()


class BankAccountWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testadmin",
            email="testadmin@example.com",
            password="testpassword123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_bank_account_crud_and_balances(self):
        # 1. Create bank account with opening balance
        create_payload = {
            "bankName": "Meezan Bank",
            "accountTitle": "Harmony Mill Master Operating",
            "accountNumber": "01020304050607",
            "iban": "PK36MEZN0001020304050607",
            "branchName": "Textile City Branch",
            "accountType": "Corporate",
            "openingBalance": "500000.00",
            "status": "Active",
        }
        res = self.client.post("/api/v1/bank-accounts/", create_payload, format="json")
        self.assertEqual(res.status_code, 201)
        account_id = res.data["id"]

        account = BankAccount.objects.get(pk=account_id)
        self.assertEqual(account.opening_balance, Decimal("500000.00"))
        self.assertEqual(account.current_balance, Decimal("500000.00"))
        self.assertEqual(account.total_credit, Decimal("0.00"))
        self.assertEqual(account.total_debit, Decimal("0.00"))

        # 2. Add Credit transaction (e.g. customer payment deposit)
        credit_payload = {
            "transactionType": "Credit",
            "amount": "150000.00",
            "paymentMethod": "Online Transfer",
            "referenceNumber": "TXN-998811",
            "partyName": "ABC Fabrics Client",
            "description": "Invoice #4401 payment clearance",
        }
        res = self.client.post(f"/api/v1/bank-accounts/{account_id}/add_transaction/", credit_payload, format="json")
        self.assertEqual(res.status_code, 201)

        account.refresh_from_db()
        self.assertEqual(account.total_credit, Decimal("150000.00"))
        self.assertEqual(account.current_balance, Decimal("650000.00"))

        # 3. Add Debit transaction (e.g. yarn supplier payment)
        debit_payload = {
            "transactionType": "Debit",
            "amount": "200000.00",
            "paymentMethod": "Cheque",
            "referenceNumber": "CHQ-100234",
            "partyName": "Premium Yarn Spinners Ltd",
            "description": "Payment for Yarn Intake Lot #901",
        }
        res = self.client.post(f"/api/v1/bank-accounts/{account_id}/add_transaction/", debit_payload, format="json")
        self.assertEqual(res.status_code, 201)

        account.refresh_from_db()
        self.assertEqual(account.total_debit, Decimal("200000.00"))
        self.assertEqual(account.current_balance, Decimal("450000.00"))  # 500k + 150k - 200k = 450k

        # 4. Check transactions list endpoint
        res = self.client.get(f"/api/v1/bank-accounts/{account_id}/transactions/")
        self.assertEqual(res.status_code, 200)
        results = res.data.get("results", res.data)
        self.assertEqual(len(results), 2)

        # 5. Check summary endpoint
        res = self.client.get("/api/v1/bank-accounts/summary/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["totalAccounts"], 1)
        self.assertEqual(Decimal(str(res.data["totalCurrentBalance"])), Decimal("450000.00"))
        self.assertEqual(Decimal(str(res.data["totalCredits"])), Decimal("150000.00"))
        self.assertEqual(Decimal(str(res.data["totalDebits"])), Decimal("200000.00"))

        # 6. Delete account
        res = self.client.delete(f"/api/v1/bank-accounts/{account_id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(BankAccount.objects.filter(pk=account_id).exists())
        self.assertEqual(BankTransaction.objects.filter(account_id=account_id).count(), 0)
