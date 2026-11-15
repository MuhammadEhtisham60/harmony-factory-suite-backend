"""
Comprehensive CRUD API tests across core factory modules:
- Suppliers (/api/v1/purchase/suppliers/)
- Customers (/api/v1/sales/customers/)
- Looms (/api/v1/factory/looms/)
- Beams (/api/v1/factory/beams/)
- Cloth Names (/api/v1/cloth-names/)
- Inventory Categories, Units, Items, Purchases, Transactions, Ledger (/api/v1/inventory/...)
- Worker Salary: Workers, Attendance, Advances, Salary Periods, Payments, Ledger (/api/v1/workers/, etc.)
- Bank Accounts & Transactions (/api/v1/bank-accounts/, /api/v1/bank-transactions/)
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from factory.bank_account.models import BankAccount, BankTransaction
from factory.inventory.item.models import InventoryItem
from factory.inventory.ledger.models import InventoryLedger
from factory.worker_salary.models import Worker, WorkerSalaryLedger


class AppCRUDAPITests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="crud_admin",
            email="crud_admin@example.com",
            password="AdminPassword123!",
        )
        self.client.force_authenticate(user=self.admin)

    def test_supplier_crud(self):
        # Create
        res = self.client.post(
            "/api/v1/purchase/suppliers/",
            {
                "supplierName": "Alpha Yarn Traders",
                "companyName": "Alpha Pvt Ltd",
                "phone": "0300-1112233",
                "email": "alpha@example.com",
                "supplierType": "Yarn",
                "status": "Active",
                "bankAccounts": [
                    {
                        "bankName": "Meezan Bank",
                        "accountTitle": "Alpha Pvt Ltd",
                        "accountNumber": "0101-99887766",
                        "isPrimary": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        sup_id = res.data["data"]["id"]
        self.assertEqual(len(res.data["data"]["bankAccounts"]), 1)

        # List & Stats & Choices
        self.assertEqual(self.client.get("/api/v1/purchase/suppliers/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/purchase/suppliers/stats/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/purchase/suppliers/choices/").status_code, status.HTTP_200_OK)

        # Retrieve
        res_get = self.client.get(f"/api/v1/purchase/suppliers/{sup_id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["data"]["supplierName"], "Alpha Yarn Traders")

        # Update (PATCH)
        res_patch = self.client.patch(
            f"/api/v1/purchase/suppliers/{sup_id}/",
            {"supplierName": "Alpha Yarn Updated"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["data"]["supplierName"], "Alpha Yarn Updated")

        # Delete
        res_del = self.client.delete(f"/api/v1/purchase/suppliers/{sup_id}/")
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)

    def test_customer_crud(self):
        res = self.client.post(
            "/api/v1/sales/customers/",
            {
                "customerName": "Beta Fabrics",
                "companyName": "Beta Mills",
                "phone": "0301-2223344",
                "contactPerson": "Ali Raza",
                "customerType": "Wholesaler",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        cust_id = res.data["data"]["id"]

        self.assertEqual(self.client.get("/api/v1/sales/customers/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/sales/customers/stats/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/sales/customers/choices/").status_code, status.HTTP_200_OK)

        res_patch = self.client.patch(
            f"/api/v1/sales/customers/{cust_id}/",
            {"status": "Inactive"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["data"]["status"], "Inactive")

        res_del = self.client.delete(f"/api/v1/sales/customers/{cust_id}/")
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)

    def test_loom_and_beam_and_cloth_name_crud(self):
        # Loom CRUD
        res_loom = self.client.post(
            "/api/v1/factory/looms/",
            {
                "loomCode": "L-CRUD-01",
                "loomName": "Picanol OmniPlus",
                "modelNumber": "OMNI-2026",
                "location": "Shed A",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(res_loom.status_code, status.HTTP_201_CREATED, res_loom.data)
        loom_id = res_loom.data["data"]["id"]
        self.assertEqual(self.client.get("/api/v1/factory/looms/stats/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.patch(f"/api/v1/factory/looms/{loom_id}/", {"location": "Shed B"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(f"/api/v1/factory/looms/{loom_id}/").status_code, status.HTTP_200_OK)

        # Beam CRUD
        res_beam = self.client.post(
            "/api/v1/factory/beams/",
            {
                "beamNumber": "BM-CRUD-01",
                "beamName": "Test Beam",
                "yarnCount": "40/1",
                "width": "64.00",
                "status": "Available",
            },
            format="json",
        )
        self.assertEqual(res_beam.status_code, status.HTTP_201_CREATED, res_beam.data)
        beam_id = res_beam.data["data"]["id"]
        self.assertEqual(self.client.patch(f"/api/v1/factory/beams/{beam_id}/", {"beamName": "Updated Beam"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(f"/api/v1/factory/beams/{beam_id}/").status_code, status.HTTP_200_OK)

        # ClothName CRUD
        res_cn = self.client.post(
            "/api/v1/cloth-names/",
            {
                "name": "Poplin 60x60 Test",
                "warpCount": "60/1",
                "weftCount": "60/1",
                "reedCount": "80",
                "pickCount": "80",
                "reedWidth": "63",
            },
            format="json",
        )
        self.assertEqual(res_cn.status_code, status.HTTP_201_CREATED, res_cn.data)
        cn_id = res_cn.data["data"]["id"]
        self.assertEqual(self.client.get(f"/api/v1/cloth-names/{cn_id}/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.patch(f"/api/v1/cloth-names/{cn_id}/", {"reedWidth": "65"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(f"/api/v1/cloth-names/{cn_id}/").status_code, status.HTTP_200_OK)

    def test_inventory_full_crud_and_payment_flow(self):
        # 1. Category & Unit CRUD
        res_cat = self.client.post("/api/v1/inventory/categories/", {"name": "Spare Parts CRUD"}, format="json")
        self.assertEqual(res_cat.status_code, status.HTTP_201_CREATED, res_cat.data)
        cat_id = res_cat.data["data"]["id"]

        res_unit = self.client.post("/api/v1/inventory/units/", {"name": "Piece CRUD", "abbreviation": "Pcs"}, format="json")
        self.assertEqual(res_unit.status_code, status.HTTP_201_CREATED, res_unit.data)
        unit_id = res_unit.data["data"]["id"]

        res_sup = self.client.post("/api/v1/purchase/suppliers/", {"supplierName": "Spares Co", "phone": "0302-1112233", "status": "Active"}, format="json")
        self.assertEqual(res_sup.status_code, status.HTTP_201_CREATED)
        sup_id = res_sup.data["data"]["id"]

        res_bank = self.client.post(
            "/api/v1/bank-accounts/",
            {
                "bankName": "HBL",
                "accountTitle": "Factory Main",
                "accountNumber": "HBL-CRUD-001",
                "openingBalance": "100000.00",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(res_bank.status_code, status.HTTP_201_CREATED, res_bank.data)
        bank_id = res_bank.data["id"]

        # 2. Item CRUD (with opening stock = 10)
        res_item = self.client.post(
            "/api/v1/inventory/items/",
            {
                "item_name": "Gripper Right",
                "category": cat_id,
                "unit": unit_id,
                "opening_stock": 10,
                "minimum_stock_level": 5,
                "purchase_price": 1000,
                "preferred_supplier": sup_id,
            },
            format="json",
        )
        self.assertEqual(res_item.status_code, status.HTTP_201_CREATED, res_item.data)
        item_id = res_item.data["data"]["id"]
        self.assertEqual(Decimal(res_item.data["data"]["currentStock"]), Decimal("10"))

        # Update Item
        res_item_patch = self.client.patch(
            f"/api/v1/inventory/items/{item_id}/",
            {"storage_location": "Rack B-2"},
            format="json",
        )
        self.assertEqual(res_item_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_item_patch.data["data"]["storageLocation"], "Rack B-2")

        # Stats & Item Ledger
        self.assertEqual(self.client.get("/api/v1/inventory/stats/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f"/api/v1/inventory/items/{item_id}/ledger/").status_code, status.HTTP_200_OK)

        # 3. Purchase CRUD + Confirm + Pay
        today = str(timezone.localdate())
        res_po = self.client.post(
            "/api/v1/inventory/purchases/",
            {
                "supplier": sup_id,
                "purchase_date": today,
                "reference_number": "BILL-101",
                "items": [
                    {
                        "inventory_item": item_id,
                        "quantity": 5,
                        "unit_price": 1000,
                        "total_price": 5000,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res_po.status_code, status.HTTP_201_CREATED, res_po.data)
        po_id = res_po.data["data"]["id"]

        # Confirm purchase
        res_confirm = self.client.post(f"/api/v1/inventory/purchases/{po_id}/confirm/", {}, format="json")
        self.assertEqual(res_confirm.status_code, status.HTTP_200_OK, res_confirm.data)
        item_obj = InventoryItem.objects.get(pk=item_id)
        self.assertEqual(item_obj.current_stock, Decimal("15"))

        # Pay purchase via bank account
        res_pay = self.client.post(
            f"/api/v1/inventory/purchases/{po_id}/pay/",
            {
                "paymentAmount": 2000,
                "paymentMethod": "Online Transfer",
                "bankAccountId": bank_id,
                "paymentDate": today,
            },
            format="json",
        )
        self.assertEqual(res_pay.status_code, status.HTTP_200_OK, res_pay.data)
        self.assertEqual(res_pay.data["data"]["paymentStatus"], "Partially Paid")
        bank_obj = BankAccount.objects.get(pk=bank_id)
        self.assertEqual(bank_obj.current_balance, Decimal("98000.00"))

        # 4. Transaction Create + Stock Validation + 405 on Delete
        res_tx = self.client.post(
            "/api/v1/inventory/transactions/",
            {
                "inventory_item": item_id,
                "transaction_type": "Stock Out",
                "quantity": 3,
                "transaction_date": today,
                "issued_to": "Aslam",
                "related_area": "Loom 1",
            },
            format="json",
        )
        self.assertEqual(res_tx.status_code, status.HTTP_201_CREATED, res_tx.data)
        tx_id = res_tx.data["data"]["id"]
        item_obj.refresh_from_db()
        self.assertEqual(item_obj.current_stock, Decimal("12"))

        # Insufficient stock check
        res_tx_fail = self.client.post(
            "/api/v1/inventory/transactions/",
            {
                "inventory_item": item_id,
                "transaction_type": "Stock Out",
                "quantity": 999,
                "transaction_date": today,
            },
            format="json",
        )
        self.assertEqual(res_tx_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # Immutable transaction delete returns 405
        self.assertEqual(
            self.client.delete(f"/api/v1/inventory/transactions/{tx_id}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        # 5. Inventory Ledger list & direct ledger payment
        res_ledger = self.client.get("/api/v1/inventory/ledger/")
        self.assertEqual(res_ledger.status_code, status.HTTP_200_OK)
        open_entry = InventoryLedger.objects.filter(inventory_item_id=item_id, transaction_type="Opening Stock").first()
        res_lpay = self.client.post(
            f"/api/v1/inventory/ledger/{open_entry.id}/pay/",
            {"paymentStatus": "Paid", "paymentMethod": "Cash"},
            format="json",
        )
        self.assertEqual(res_lpay.status_code, status.HTTP_200_OK, res_lpay.data)
        self.assertEqual(res_lpay.data["data"]["paymentStatus"], "Paid")

    def test_worker_salary_full_crud_and_bank_sync(self):
        today = str(timezone.localdate())

        # Bank account for salary & advance payments
        res_bank = self.client.post(
            "/api/v1/bank-accounts/",
            {
                "bankName": "MCB",
                "accountTitle": "Payroll Account",
                "accountNumber": "MCB-PAY-001",
                "openingBalance": "50000.00",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(res_bank.status_code, status.HTTP_201_CREATED)
        bank_id = res_bank.data["id"]

        # 1. Worker CRUD
        res_wrk = self.client.post(
            "/api/v1/workers/",
            {
                "name": "Tariq Mahmood",
                "loom_type": "Power Loom",
                "daily_wage_rate": "1500.00",
                "preferred_payment_cycle": "15 Days",
                "status": "Active",
            },
            format="json",
        )
        self.assertEqual(res_wrk.status_code, status.HTTP_201_CREATED, res_wrk.data)
        wrk_id = res_wrk.data["id"]

        self.assertEqual(self.client.get("/api/v1/workers/summary/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.patch(f"/api/v1/workers/{wrk_id}/", {"phone": "0300-5556677"}, format="json").status_code,
            status.HTTP_200_OK,
        )

        # 2. Attendance Create, Update, Delete (unprocessed)
        res_att = self.client.post(
            "/api/v1/worker-attendance/",
            {
                "worker": wrk_id,
                "date": today,
                "status": "Present",
            },
            format="json",
        )
        self.assertEqual(res_att.status_code, status.HTTP_201_CREATED, res_att.data)
        att_id = res_att.data["id"]
        wrk = Worker.objects.get(pk=wrk_id)
        self.assertEqual(wrk.current_balance, Decimal("1500.00"))

        # Update attendance to Half Day -> earned should become 750.00
        res_att_upd = self.client.patch(
            f"/api/v1/worker-attendance/{att_id}/",
            {"status": "Half Day"},
            format="json",
        )
        self.assertEqual(res_att_upd.status_code, status.HTTP_200_OK, res_att_upd.data)
        wrk.refresh_from_db()
        self.assertEqual(wrk.current_balance, Decimal("750.00"))

        # Delete attendance -> ledger entry removed, balance back to 0.00
        res_att_del = self.client.delete(f"/api/v1/worker-attendance/{att_id}/")
        self.assertEqual(res_att_del.status_code, status.HTTP_204_NO_CONTENT)
        wrk.refresh_from_db()
        self.assertEqual(wrk.current_balance, Decimal("0.00"))

        # Re-record Present attendance for salary period test
        res_att2 = self.client.post(
            "/api/v1/worker-attendance/",
            {"worker": wrk_id, "date": today, "status": "Present"},
            format="json",
        )
        self.assertEqual(res_att2.status_code, status.HTTP_201_CREATED)

        # 3. Worker Advance via Bank (tests BankTransaction account=bank_account fix!)
        res_adv = self.client.post(
            "/api/v1/worker-advances/",
            {
                "worker": wrk_id,
                "amount": "500.00",
                "advance_date": today,
                "payment_method": "Online Transfer",
                "bank_account": bank_id,
                "notes": "Test advance",
            },
            format="json",
        )
        self.assertEqual(res_adv.status_code, status.HTTP_201_CREATED, res_adv.data)
        bank_obj = BankAccount.objects.get(pk=bank_id)
        self.assertEqual(bank_obj.current_balance, Decimal("49500.00"))

        # 4. Salary Period Preview & Finalize & Pay via Bank
        res_prev = self.client.post(
            "/api/v1/power-loom-salary/preview/",
            {"worker": wrk_id, "start_date": today, "end_date": today},
            format="json",
        )
        self.assertEqual(res_prev.status_code, status.HTTP_200_OK, res_prev.data)
        self.assertEqual(Decimal(res_prev.data["net_payable_balance"]), Decimal("1000.00"))

        res_fin = self.client.post(
            "/api/v1/power-loom-salary/finalize/",
            {"worker": wrk_id, "start_date": today, "end_date": today},
            format="json",
        )
        self.assertEqual(res_fin.status_code, status.HTTP_201_CREATED, res_fin.data)
        period_id = res_fin.data["id"]

        res_spay = self.client.post(
            f"/api/v1/power-loom-salary/{period_id}/pay/",
            {
                "amount": "1000.00",
                "payment_date": today,
                "payment_method": "Online Transfer",
                "bank_account": bank_id,
            },
            format="json",
        )
        self.assertEqual(res_spay.status_code, status.HTTP_201_CREATED, res_spay.data)
        self.assertEqual(res_spay.data["salary_period"]["payment_status"], "Paid")
        bank_obj.refresh_from_db()
        self.assertEqual(bank_obj.current_balance, Decimal("48500.00"))

        # 5. Ledger & Stats endpoints
        self.assertEqual(self.client.get(f"/api/v1/workers/{wrk_id}/ledger/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/worker-salary-ledger/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/v1/worker-salary-ledger/stats/").status_code, status.HTTP_200_OK)

