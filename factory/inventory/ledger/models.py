"""
InventoryLedger and InventoryPayment models for the Inventory module.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

from factory.inventory.item.models import InventoryItem
from factory.purchase.supplier.models import Supplier


class InventoryLedger(models.Model):
    """
    Audit & financial ledger for every stock movement of an inventory item.
    Created automatically by services and updated with payment tracking.
    """

    class TransactionTypeChoices(models.TextChoices):
        OPENING_STOCK = "Opening Stock", "Opening Stock"
        STOCK_IN = "Stock In", "Stock In"
        STOCK_OUT = "Stock Out", "Stock Out"
        ADJUSTMENT_IN = "Adjustment In", "Adjustment In"
        ADJUSTMENT_OUT = "Adjustment Out", "Adjustment Out"

    class PaymentStatusChoices(models.TextChoices):
        PENDING = "Pending", "Pending"
        PARTIALLY_PAID = "Partially Paid", "Partially Paid"
        PAID = "Paid", "Paid"

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    transaction_date = models.DateField()
    transaction_number = models.CharField(max_length=100)
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionTypeChoices.choices,
    )

    quantity_in = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_out = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    running_balance = models.DecimalField(max_digits=12, decimal_places=4)

    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
    )

    reference_id = models.IntegerField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True, default="")

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_ledger_entries",
    )

    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_ledger_entries",
    )

    class Meta:
        ordering = ["transaction_date", "id"]
        verbose_name = "Inventory Ledger"
        verbose_name_plural = "Inventory Ledger Entries"

    def recompute_payment_fields(self, explicit_status=None):
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.amount_paid or 0))
        if paid < Decimal("0"):
            paid = Decimal("0")
        due = total - paid
        if due < Decimal("0"):
            due = Decimal("0")
        self.amount_paid = paid
        self.amount_due = due
        if explicit_status in dict(self.PaymentStatusChoices.choices):
            self.payment_status = explicit_status
        else:
            if total > Decimal("0") and paid >= total:
                self.payment_status = self.PaymentStatusChoices.PAID
            elif paid > Decimal("0"):
                self.payment_status = self.PaymentStatusChoices.PARTIALLY_PAID
            else:
                self.payment_status = self.PaymentStatusChoices.PENDING

    def __str__(self):
        return f"{self.transaction_number} – {self.transaction_type} ({self.inventory_item})"


class InventoryPayment(models.Model):
    """
    Records a payment made against an InventoryLedger entry and/or InventoryPurchase.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "Cash", "Cash"
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer / IBFT"
        CHEQUE = "Cheque", "Cheque"
        PAY_ORDER = "Pay Order", "Pay Order"
        OTHER = "Other", "Other"

    ledger_entry = models.ForeignKey(
        InventoryLedger,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )
    purchase = models.ForeignKey(
        "factory.InventoryPurchase",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_payments",
    )
    bank_account = models.ForeignKey(
        "factory.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_payments",
    )
    bank_transaction = models.OneToOneField(
        "factory.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_payment",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    reference_number = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_payments",
    )

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Inventory Payment"
        verbose_name_plural = "Inventory Payments"

    def __str__(self):
        target = (
            self.ledger_entry.transaction_number
            if self.ledger_entry
            else (self.purchase.purchase_number if self.purchase else "Inventory")
        )
        return f"Payment #{self.id} for {target} - Rs. {self.amount}"

    def _sync_bank_transaction(self):
        from factory.bank_account.models import BankTransaction

        if self.bank_account and Decimal(str(self.amount or 0)) > Decimal("0"):
            s_name = (
                self.supplier.supplier_name
                if self.supplier
                else (
                    self.ledger_entry.supplier.supplier_name
                    if self.ledger_entry and self.ledger_entry.supplier
                    else "Inventory Supplier"
                )
            )
            ref_label = (
                self.ledger_entry.transaction_number
                if self.ledger_entry
                else (self.purchase.purchase_number if self.purchase else "")
            )
            desc = (
                f"Inventory Payment ({ref_label}) to {s_name}"
                + (f" - {self.notes}" if self.notes else "")
            )

            bt_method = self.payment_method
            valid_methods = set(dict(BankTransaction.PaymentMethod.choices).keys())
            if bt_method not in valid_methods:
                bt_method = BankTransaction.PaymentMethod.ONLINE_TRANSFER

            if self.bank_transaction_id:
                tx = self.bank_transaction
                tx.account = self.bank_account
                tx.amount = self.amount
                tx.date = self.payment_date
                tx.payment_method = bt_method
                tx.reference_number = self.reference_number or ""
                tx.party_name = s_name
                tx.description = desc
                tx.save()
            else:
                tx = BankTransaction.objects.create(
                    account=self.bank_account,
                    transaction_type=BankTransaction.TransactionType.DEBIT,
                    amount=self.amount,
                    date=self.payment_date,
                    payment_method=bt_method,
                    reference_number=self.reference_number or "",
                    party_name=s_name,
                    description=desc,
                    created_by=self.created_by,
                )
                self.bank_transaction = tx
                InventoryPayment.objects.filter(id=self.id).update(bank_transaction=tx)
        else:
            if self.bank_transaction_id:
                tx = self.bank_transaction
                InventoryPayment.objects.filter(id=self.id).update(bank_transaction=None)
                self.bank_transaction = None
                tx.delete()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._sync_bank_transaction()

