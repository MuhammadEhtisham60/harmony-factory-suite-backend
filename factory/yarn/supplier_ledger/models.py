"""
Yarn Supplier Payment model for tracking payments made to yarn suppliers.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class YarnSupplierPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer / IBFT"
        CHEQUE = "Cheque", "Cheque"
        CASH = "Cash", "Cash"
        PAY_ORDER = "Pay Order", "Pay Order"
        OTHER = "Other", "Other"

    supplier = models.ForeignKey(
        "factory.Supplier",
        on_delete=models.PROTECT,
        related_name="yarn_payments",
        help_text="Supplier receiving payment"
    )
    yarn_intake = models.ForeignKey(
        "factory.YarnIntake",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Specific Yarn Intake batch this payment is allocated to (optional)"
    )
    bank_account = models.ForeignKey(
        "factory.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yarn_supplier_payments",
        help_text="Bank account the payment was made from (optional)"
    )
    bank_transaction = models.OneToOneField(
        "factory.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yarn_supplier_payment",
        help_text="Linked debit bank transaction deducting money from bank account"
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Payment monetary amount"
    )
    payment_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE_TRANSFER
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Cheque number, IBFT reference, or transaction ID"
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Payment remarks or narration"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_yarn_supplier_payments"
    )

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Yarn Supplier Payment"
        verbose_name_plural = "Yarn Supplier Payments"

    def __str__(self):
        s_name = self.supplier.supplier_name if self.supplier else "N/A"
        return f"Payment #{self.id} to {s_name} - Rs. {self.amount}"

    def _sync_bank_transaction(self):
        """
        Deducts the payment amount from the selected bank account by creating
        or updating a linked Debit BankTransaction.
        If bank_account is removed, cleans up any existing Debit BankTransaction.
        """
        from factory.bank_account.models import BankTransaction

        if self.bank_account:
            s_name = self.supplier.supplier_name if self.supplier else "Supplier"
            s_code = self.supplier.supplier_code if self.supplier else ""
            desc = (
                f"Payment to Yarn Supplier {s_name} ({s_code})"
                + (f" for Batch #{self.yarn_intake_id}" if self.yarn_intake_id else "")
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
                YarnSupplierPayment.objects.filter(id=self.id).update(bank_transaction=tx)
        else:
            if self.bank_transaction_id:
                tx = self.bank_transaction
                YarnSupplierPayment.objects.filter(id=self.id).update(bank_transaction=None)
                self.bank_transaction = None
                tx.delete()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._sync_bank_transaction()
        if self.yarn_intake_id:
            # Sync intake amount_paid from all related payments
            total_paid = self.yarn_intake.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
            self.yarn_intake.amount_paid = total_paid
            self.yarn_intake.save(update_fields=["amount_paid", "amount_due", "payment_status", "updated_at"])

    def delete(self, *args, **kwargs):
        intake = self.yarn_intake
        tx = self.bank_transaction
        super().delete(*args, **kwargs)
        if tx:
            tx.delete()
        if intake:
            total_paid = intake.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
            intake.amount_paid = total_paid
            intake.save(update_fields=["amount_paid", "amount_due", "payment_status", "updated_at"])
