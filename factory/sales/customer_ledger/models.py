"""
Models for Cloth Sales and Customer Payments (Cloth Customer Ledger).
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class ClothSale(models.Model):
    """
    Records cloth fabric dispatched / sold to a customer.
    Creates an accounts-receivable (debit) entry on the customer's ledger.
    """
    class StatusChoices(models.TextChoices):
        DELIVERED = "Delivered", "Delivered"
        DISPATCHED = "Dispatched", "Dispatched"
        PENDING = "Pending", "Pending"
        CANCELLED = "Cancelled", "Cancelled"

    class PaymentStatusChoices(models.TextChoices):
        PAID = "Paid", "Paid"
        PARTIAL = "Partial", "Partially Paid"
        PENDING = "Pending", "Unpaid / Pending"

    invoice_number = models.CharField(
        max_length=60,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Unique Sale Invoice identifier (e.g. INV-C-2026-0001)"
    )

    customer = models.ForeignKey(
        "factory.Customer",
        on_delete=models.PROTECT,
        related_name="cloth_sales",
        help_text="Customer receiving the cloth dispatch"
    )

    cloth_name = models.ForeignKey(
        "factory.ClothName",
        on_delete=models.PROTECT,
        related_name="cloth_sales",
        help_text="Cloth quality / fabric specification"
    )

    sale_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
        help_text="Date of sale / dispatch"
    )

    quantity_meters = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        help_text="Length of cloth in meters"
    )

    rate_per_meter = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        help_text="Rate per meter in PKR"
    )

    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total invoice amount in PKR (quantity * rate)"
    )

    amount_paid = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total amount paid against this invoice"
    )

    amount_due = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Outstanding balance on this invoice"
    )

    payment_status = models.CharField(
        max_length=50,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        db_index=True
    )

    status = models.CharField(
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.DELIVERED,
        db_index=True
    )

    delivery_challan_no = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Delivery Challan / Gate Pass / Bilty number"
    )

    vehicle_no = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Transport vehicle registration number"
    )

    driver_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Driver or transporter name"
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Order narration, terms, or remarks"
    )

    deduct_from_stock = models.BooleanField(
        default=False,
        help_text="Whether this sale deducted meters from master clean cloth inventory"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cloth_sales"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_cloth_sales"
    )

    class Meta:
        ordering = ["-sale_date", "-id"]
        verbose_name = "Cloth Sale"
        verbose_name_plural = "Cloth Sales"
        indexes = [
            models.Index(fields=["customer", "sale_date"], name="factory_cs_cus_date_idx"),
            models.Index(fields=["cloth_name"], name="factory_cs_cloth_idx"),
        ]

    def __str__(self):
        c_name = self.customer.customer_name if self.customer else "N/A"
        cloth = self.cloth_name.name if self.cloth_name else "Cloth"
        return f"{self.invoice_number} - {c_name} ({cloth}, {self.quantity_meters}m)"

    def clean(self):
        super().clean()
        if self.quantity_meters is not None and self.rate_per_meter is not None:
            calc_total = (Decimal(str(self.quantity_meters)) * Decimal(str(self.rate_per_meter))).quantize(Decimal("0.01"))
            if not self.total_amount or self.total_amount == Decimal("0.00"):
                self.total_amount = calc_total

    def save(self, *args, **kwargs):
        # Auto-generate invoice number if missing
        if not self.invoice_number:
            year = timezone.localdate().year
            last_sale = ClothSale.objects.order_by("-id").first()
            next_id = (last_sale.id + 1) if last_sale else 1
            self.invoice_number = f"INV-C-{year}-{next_id:04d}"

        # Calculate totals
        if self.quantity_meters is not None and self.rate_per_meter is not None:
            if not self.total_amount or self.total_amount == Decimal("0.00"):
                self.total_amount = (Decimal(str(self.quantity_meters)) * Decimal(str(self.rate_per_meter))).quantize(Decimal("0.01"))

        if self.amount_paid is None:
            self.amount_paid = Decimal("0.00")

        self.amount_due = max(Decimal("0.00"), self.total_amount - self.amount_paid)

        if self.amount_paid >= self.total_amount and self.total_amount > Decimal("0.00"):
            self.payment_status = self.PaymentStatusChoices.PAID
        elif self.amount_paid > Decimal("0.00"):
            self.payment_status = self.PaymentStatusChoices.PARTIAL
        else:
            self.payment_status = self.PaymentStatusChoices.PENDING

        super().save(*args, **kwargs)


class ClothCustomerPayment(models.Model):
    """
    Records monetary payments received from customers for cloth sales.
    Creates an accounts-receivable reduction (credit) entry on the customer's ledger.
    Optionally links to a factory BankAccount, automatically recording a CREDIT BankTransaction.
    """
    class PaymentMethod(models.TextChoices):
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer / IBFT"
        CHEQUE = "Cheque", "Cheque"
        CASH = "Cash", "Cash"
        PAY_ORDER = "Pay Order", "Pay Order"
        OTHER = "Other", "Other"

    payment_number = models.CharField(
        max_length=60,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Unique receipt identifier (e.g. CPAY-2026-0001)"
    )

    customer = models.ForeignKey(
        "factory.Customer",
        on_delete=models.PROTECT,
        related_name="cloth_payments",
        help_text="Customer making the payment"
    )

    cloth_sale = models.ForeignKey(
        ClothSale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Specific Cloth Sale / Invoice this payment is allocated against (optional)"
    )

    bank_account = models.ForeignKey(
        "factory.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloth_customer_payments",
        help_text="Factory Bank Account into which the funds were received/deposited (optional)"
    )

    bank_transaction = models.OneToOneField(
        "factory.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloth_customer_payment",
        help_text="Linked Credit bank transaction depositing money into bank account"
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Payment monetary amount in PKR"
    )

    payment_date = models.DateField(
        default=timezone.localdate,
        db_index=True
    )

    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE_TRANSFER
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Cheque number, IBFT transaction ID, or deposit slip number"
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
        related_name="created_cloth_customer_payments"
    )

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Cloth Customer Payment"
        verbose_name_plural = "Cloth Customer Payments"

    def __str__(self):
        c_name = self.customer.customer_name if self.customer else "N/A"
        return f"{self.payment_number or f'Payment #{self.id}'} from {c_name} - Rs. {self.amount}"

    def _sync_bank_transaction(self):
        """
        Deposits the received customer payment into the selected factory bank account
        by creating or updating a linked CREDIT BankTransaction.
        """
        from factory.bank_account.models import BankTransaction

        if self.bank_account:
            c_name = self.customer.customer_name if self.customer else "Customer"
            c_code = self.customer.customer_code if self.customer else ""
            desc = (
                f"Receipt from Customer {c_name} ({c_code})"
                + (f" for Cloth Invoice #{self.cloth_sale.invoice_number}" if self.cloth_sale else "")
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
                tx.party_name = c_name
                tx.description = desc
                tx.save()
            else:
                tx = BankTransaction.objects.create(
                    account=self.bank_account,
                    transaction_type=BankTransaction.TransactionType.CREDIT,
                    amount=self.amount,
                    date=self.payment_date,
                    payment_method=bt_method,
                    reference_number=self.reference_number or "",
                    party_name=c_name,
                    description=desc,
                    created_by=self.created_by,
                )
                self.bank_transaction = tx
                ClothCustomerPayment.objects.filter(id=self.id).update(bank_transaction=tx)
        else:
            if self.bank_transaction_id:
                tx = self.bank_transaction
                ClothCustomerPayment.objects.filter(id=self.id).update(bank_transaction=None)
                self.bank_transaction = None
                tx.delete()

    def save(self, *args, **kwargs):
        if not self.payment_number:
            year = timezone.localdate().year
            last_pay = ClothCustomerPayment.objects.order_by("-id").first()
            next_id = (last_pay.id + 1) if last_pay else 1
            self.payment_number = f"CPAY-{year}-{next_id:04d}"

        super().save(*args, **kwargs)
        self._sync_bank_transaction()

        if self.cloth_sale_id:
            total_paid = self.cloth_sale.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
            self.cloth_sale.amount_paid = total_paid
            self.cloth_sale.amount_due = max(Decimal("0.00"), self.cloth_sale.total_amount - total_paid)
            if total_paid >= self.cloth_sale.total_amount and self.cloth_sale.total_amount > Decimal("0.00"):
                self.cloth_sale.payment_status = ClothSale.PaymentStatusChoices.PAID
            elif total_paid > Decimal("0.00"):
                self.cloth_sale.payment_status = ClothSale.PaymentStatusChoices.PARTIAL
            else:
                self.cloth_sale.payment_status = ClothSale.PaymentStatusChoices.PENDING
            self.cloth_sale.save(update_fields=["amount_paid", "amount_due", "payment_status", "updated_at"])

    def delete(self, *args, **kwargs):
        sale = self.cloth_sale
        tx = self.bank_transaction
        super().delete(*args, **kwargs)
        if tx:
            tx.delete()
        if sale:
            total_paid = sale.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
            sale.amount_paid = total_paid
            sale.amount_due = max(Decimal("0.00"), sale.total_amount - total_paid)
            if total_paid >= sale.total_amount and sale.total_amount > Decimal("0.00"):
                sale.payment_status = ClothSale.PaymentStatusChoices.PAID
            elif total_paid > Decimal("0.00"):
                sale.payment_status = ClothSale.PaymentStatusChoices.PARTIAL
            else:
                sale.payment_status = ClothSale.PaymentStatusChoices.PENDING
            sale.save(update_fields=["amount_paid", "amount_due", "payment_status", "updated_at"])
