"""
Serializers for Bank Accounts and Bank Transactions.
Supports full CRUD with camelCase and snake_case interop,
and balance calculations.
"""

from decimal import Decimal
from rest_framework import serializers
from .models import BankAccount, BankTransaction


class BankTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Bank Transactions (Credits & Debits).
    """
    accountId = serializers.IntegerField(source="account_id", read_only=True)
    accountTitle = serializers.CharField(source="account.account_title", read_only=True)
    bankName = serializers.CharField(source="account.bank_name", read_only=True)
    accountNumber = serializers.CharField(source="account.account_number", read_only=True)

    transactionType = serializers.CharField(source="transaction_type", required=False)
    paymentMethod = serializers.CharField(source="payment_method", required=False)
    referenceNumber = serializers.CharField(source="reference_number", required=False, allow_blank=True)
    partyName = serializers.CharField(source="party_name", required=False, allow_blank=True)
    runningBalance = serializers.DecimalField(
        source="running_balance",
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "account",
            "accountId",
            "accountTitle",
            "bankName",
            "accountNumber",
            "transaction_type",
            "transactionType",
            "amount",
            "date",
            "payment_method",
            "paymentMethod",
            "reference_number",
            "referenceNumber",
            "party_name",
            "partyName",
            "description",
            "running_balance",
            "runningBalance",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
            "createdBy",
            "updatedBy",
        ]
        extra_kwargs = {
            "account": {"required": False},
            "transaction_type": {"required": False},
            "payment_method": {"required": False},
            "reference_number": {"required": False, "allow_blank": True},
            "party_name": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
        }

    def get_createdBy(self, obj):
        if not obj.created_by:
            return None
        return {
            "id": obj.created_by.id,
            "username": getattr(obj.created_by, "username", ""),
            "name": getattr(obj.created_by, "get_full_name", lambda: "")() or getattr(obj.created_by, "username", ""),
        }

    def get_updatedBy(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "username": getattr(obj.updated_by, "username", ""),
            "name": getattr(obj.updated_by, "get_full_name", lambda: "")() or getattr(obj.updated_by, "username", ""),
        }

    def to_internal_value(self, data):
        ret = {}

        # Account resolution
        account_val = data.get("account") or data.get("accountId") or data.get("account_id")
        if account_val is not None and account_val != "":
            if isinstance(account_val, BankAccount):
                ret["account"] = account_val
            elif isinstance(account_val, (int, str)) and str(account_val).isdigit():
                try:
                    ret["account"] = BankAccount.objects.get(pk=int(account_val))
                except BankAccount.DoesNotExist:
                    raise serializers.ValidationError({"account": f"BankAccount id {account_val} does not exist."})
            else:
                raise serializers.ValidationError({"account": "Invalid account value."})

        # Transaction type
        tt = data.get("transactionType") or data.get("transaction_type")
        if tt:
            clean_tt = str(tt).capitalize()
            if clean_tt in ["Credit", "Debit"]:
                ret["transaction_type"] = clean_tt
            else:
                raise serializers.ValidationError({"transactionType": "Must be 'Credit' or 'Debit'."})

        # Amount
        amt = data.get("amount")
        if amt is not None and amt != "":
            try:
                dec_amt = Decimal(str(amt))
                if dec_amt <= 0:
                    raise serializers.ValidationError({"amount": "Amount must be strictly greater than zero."})
                ret["amount"] = dec_amt
            except (ValueError, TypeError):
                raise serializers.ValidationError({"amount": "Invalid amount format."})

        # Date
        dt = data.get("date")
        if dt:
            if hasattr(dt, "date"):
                ret["date"] = dt.date()
            elif isinstance(dt, str) and "T" in dt:
                ret["date"] = dt.split("T")[0]
            else:
                ret["date"] = dt

        # Payment method
        pm = data.get("paymentMethod") or data.get("payment_method")
        if pm:
            ret["payment_method"] = str(pm)

        # Reference number
        ref = data.get("referenceNumber") or data.get("reference_number")
        if ref is not None:
            ret["reference_number"] = str(ref).strip()

        # Party name
        party = data.get("partyName") or data.get("party_name")
        if party is not None:
            ret["party_name"] = str(party).strip()

        # Description
        desc = data.get("description") or data.get("narration") or data.get("notes")
        if desc is not None:
            ret["description"] = str(desc).strip()

        return ret

    def validate(self, attrs):
        if not self.instance:
            if "account" not in attrs and "account" not in self.context:
                raise serializers.ValidationError({"account": "Account is required."})
            if "transaction_type" not in attrs:
                raise serializers.ValidationError({"transactionType": "Transaction type (Credit / Debit) is required."})
            if "amount" not in attrs:
                raise serializers.ValidationError({"amount": "Transaction amount is required."})
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


class BankAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for Bank Account creation, view, update, and deletion.
    """
    bankName = serializers.CharField(source="bank_name")
    accountTitle = serializers.CharField(source="account_title")
    accountNumber = serializers.CharField(source="account_number")
    branchName = serializers.CharField(source="branch_name", required=False, allow_blank=True)
    branchCode = serializers.CharField(source="branch_code", required=False, allow_blank=True)
    swiftCode = serializers.CharField(source="swift_code", required=False, allow_blank=True)
    accountType = serializers.CharField(source="account_type", required=False)
    openingBalance = serializers.DecimalField(
        source="opening_balance",
        max_digits=18,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
    )
    openingDate = serializers.DateField(source="opening_date", required=False)
    currentBalance = serializers.DecimalField(
        source="current_balance",
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    totalCredit = serializers.DecimalField(
        source="total_credit",
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    totalDebit = serializers.DecimalField(
        source="total_debit",
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )

    transactionsCount = serializers.SerializerMethodField()
    lastTransactionDate = serializers.SerializerMethodField()

    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "bank_name",
            "bankName",
            "account_title",
            "accountTitle",
            "account_number",
            "accountNumber",
            "iban",
            "branch_name",
            "branchName",
            "branch_code",
            "branchCode",
            "swift_code",
            "swiftCode",
            "account_type",
            "accountType",
            "currency",
            "opening_balance",
            "openingBalance",
            "opening_date",
            "openingDate",
            "current_balance",
            "currentBalance",
            "total_credit",
            "totalCredit",
            "total_debit",
            "totalDebit",
            "status",
            "notes",
            "transactionsCount",
            "lastTransactionDate",
            "created_at",
            "createdAt",
            "updated_at",
            "updatedAt",
            "createdBy",
            "updatedBy",
        ]
        extra_kwargs = {
            "iban": {"required": False, "allow_blank": True},
            "currency": {"required": False, "default": "PKR"},
            "status": {"required": False, "default": "Active"},
            "notes": {"required": False, "allow_blank": True},
        }

    def get_transactionsCount(self, obj):
        return obj.transactions.count()

    def get_lastTransactionDate(self, obj):
        last_tx = obj.transactions.order_by("-date", "-created_at").first()
        return str(last_tx.date) if last_tx else None

    def get_createdBy(self, obj):
        if not obj.created_by:
            return None
        return {
            "id": obj.created_by.id,
            "username": getattr(obj.created_by, "username", ""),
            "name": getattr(obj.created_by, "get_full_name", lambda: "")() or getattr(obj.created_by, "username", ""),
        }

    def get_updatedBy(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "username": getattr(obj.updated_by, "username", ""),
            "name": getattr(obj.updated_by, "get_full_name", lambda: "")() or getattr(obj.updated_by, "username", ""),
        }

    def to_internal_value(self, data):
        ret = {}

        for key in ["bankName", "bank_name"]:
            if key in data and data[key] not in (None, ""):
                ret["bank_name"] = str(data[key]).strip()
                break

        for key in ["accountTitle", "account_title"]:
            if key in data and data[key] not in (None, ""):
                ret["account_title"] = str(data[key]).strip()
                break

        for key in ["accountNumber", "account_number"]:
            if key in data and data[key] not in (None, ""):
                ret["account_number"] = str(data[key]).strip()
                break

        if "iban" in data:
            ret["iban"] = str(data["iban"]).strip()

        for key in ["branchName", "branch_name"]:
            if key in data:
                ret["branch_name"] = str(data[key]).strip()
                break

        for key in ["branchCode", "branch_code"]:
            if key in data:
                ret["branch_code"] = str(data[key]).strip()
                break

        for key in ["swiftCode", "swift_code"]:
            if key in data:
                ret["swift_code"] = str(data[key]).strip()
                break

        for key in ["accountType", "account_type"]:
            if key in data and data[key]:
                ret["account_type"] = str(data[key]).strip()
                break

        if "currency" in data and data["currency"]:
            ret["currency"] = str(data["currency"]).strip().upper()

        for key in ["openingBalance", "opening_balance"]:
            if key in data and data[key] not in (None, ""):
                try:
                    ret["opening_balance"] = Decimal(str(data[key]))
                except (ValueError, TypeError):
                    raise serializers.ValidationError({"openingBalance": "Invalid decimal for opening balance."})
                break

        for key in ["openingDate", "opening_date"]:
            if key in data and data[key]:
                raw_dt = data[key]
                if hasattr(raw_dt, "date"):
                    ret["opening_date"] = raw_dt.date()
                elif isinstance(raw_dt, str) and "T" in raw_dt:
                    ret["opening_date"] = raw_dt.split("T")[0]
                else:
                    ret["opening_date"] = raw_dt
                break

        if "status" in data and data["status"]:
            ret["status"] = str(data["status"]).strip()

        for key in ["notes", "remarks"]:
            if key in data:
                ret["notes"] = str(data[key]).strip()
                break

        return ret

    def validate_account_number(self, value):
        qs = BankAccount.objects.filter(account_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A bank account with this account number already exists.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user
        instance = super().create(validated_data)
        instance.recalculate_balances()
        return instance

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        instance = super().update(instance, validated_data)
        instance.recalculate_balances()
        return instance


class BankAccountDetailSerializer(BankAccountSerializer):
    """
    Detailed serializer including recent transactions for statement/ledger view.
    """
    transactions = serializers.SerializerMethodField()

    class Meta(BankAccountSerializer.Meta):
        fields = BankAccountSerializer.Meta.fields + ["transactions"]

    def get_transactions(self, obj):
        # Return recent 50 transactions ordered by date descending
        txs = obj.transactions.order_by("-date", "-created_at")[:50]
        return BankTransactionSerializer(txs, many=True, context=self.context).data
