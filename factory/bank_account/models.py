from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class BankAccount(models.Model):
    class AccountType(models.TextChoices):
        CURRENT = "Current", "Current Account"
        SAVINGS = "Savings", "Savings Account"
        ISLAMIC = "Islamic", "Islamic Banking Account"
        CORPORATE = "Corporate", "Corporate Account"
        OTHER = "Other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"
        FROZEN = "Frozen", "Frozen"
        CLOSED = "Closed", "Closed"

    bank_name = models.CharField(max_length=255, help_text="e.g. Meezan Bank, HBL, MCB")
    account_title = models.CharField(max_length=255, help_text="Company or Account Holder Title")
    account_number = models.CharField(max_length=100, unique=True)
    iban = models.CharField(max_length=100, blank=True, default="", help_text="International Bank Account Number")
    branch_name = models.CharField(max_length=255, blank=True, default="")
    branch_code = models.CharField(max_length=50, blank=True, default="")
    swift_code = models.CharField(max_length=50, blank=True, default="")

    account_type = models.CharField(
        max_length=50,
        choices=AccountType.choices,
        default=AccountType.CURRENT,
    )
    currency = models.CharField(max_length=10, default="PKR")

    # Balances
    opening_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Starting balance at the time of account creation",
    )
    opening_date = models.DateField(default=timezone.localdate)

    current_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Opening balance + total credits - total debits",
    )
    total_credit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total sum of all incoming deposits/credits",
    )
    total_debit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total sum of all outgoing payments/debits",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True, default="")

    # Audit timestamps & user tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bank_accounts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bank_accounts",
    )

    class Meta:
        ordering = ["bank_name", "account_title"]
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"

    def __str__(self):
        return f"{self.bank_name} - {self.account_title} ({self.account_number})"

    def recalculate_balances(self):
        """
        Recalculates total_credit, total_debit and current_balance from scratch.
        """
        credits = self.transactions.filter(transaction_type="Credit").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        debits = self.transactions.filter(transaction_type="Debit").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        self.total_credit = credits
        self.total_debit = debits
        self.current_balance = self.opening_balance + credits - debits
        self.save(update_fields=["total_credit", "total_debit", "current_balance", "updated_at"])

    def save(self, *args, **kwargs):
        # On first creation, initialize current_balance with opening_balance
        if not self.pk and (self.current_balance == Decimal("0.00") or self.current_balance is None):
            self.current_balance = self.opening_balance
        super().save(*args, **kwargs)


class BankTransaction(models.Model):
    class TransactionType(models.TextChoices):
        CREDIT = "Credit", "Credit (Deposit / Inflow)"
        DEBIT = "Debit", "Debit (Withdrawal / Outflow)"

    class PaymentMethod(models.TextChoices):
        ONLINE_TRANSFER = "Online Transfer", "Online Transfer / IBFT"
        CHEQUE = "Cheque", "Cheque"
        CASH_DEPOSIT = "Cash Deposit", "Cash Deposit"
        CASH_WITHDRAWAL = "Cash Withdrawal", "Cash Withdrawal"
        PAY_ORDER = "Pay Order", "Pay Order"
        RTGS = "RTGS", "RTGS"
        WIRE = "Wire Transfer", "Wire Transfer"
        OTHER = "Other", "Other"

    account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        help_text="Credit (Inflow) or Debit (Outflow)",
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Transaction monetary amount (must be > 0)",
    )
    date = models.DateField(default=timezone.localdate)

    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE_TRANSFER,
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Cheque number, transaction ID, or bank reference",
    )
    party_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Beneficiary, supplier, customer, or recipient/sender name",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Purpose or narration of the transaction",
    )

    running_balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Account balance immediately after this transaction",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bank_transactions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bank_transactions",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Bank Transaction"
        verbose_name_plural = "Bank Transactions"

    def __str__(self):
        return f"{self.account.bank_name} - {self.transaction_type} of {self.amount} on {self.date}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Recalculate parent account totals & update running balance
        self.account.recalculate_balances()
        if is_new or not self.running_balance:
            self.running_balance = self.account.current_balance
            super().save(update_fields=["running_balance"])

    def delete(self, *args, **kwargs):
        account = self.account
        super().delete(*args, **kwargs)
        account.recalculate_balances()
