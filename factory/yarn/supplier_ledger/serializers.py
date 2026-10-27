"""
DRF Serializers for Yarn Supplier Ledger.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.purchase.supplier.models import Supplier
from factory.yarn.yarn_intake.models import YarnIntake
from factory.bank_account.models import BankAccount
from .models import YarnSupplierPayment
from .ledger import exact_str


class _ExactDecimalField(serializers.Field):
    """Serializes Decimal to plain string notation without scientific notation."""

    def to_representation(self, value):
        if value is None:
            return "0"
        return exact_str(value)


class SupplierLedgerRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    entryType = serializers.CharField(source="entry_type")
    entry_type = serializers.CharField()
    date = serializers.DateField()
    supplierId = serializers.IntegerField(source="supplier_id")
    supplier_id = serializers.IntegerField()
    supplierCode = serializers.CharField(source="supplier_code")
    supplierName = serializers.CharField(source="supplier_name")
    reference = serializers.CharField()

    yarnIntakeId = serializers.IntegerField(source="yarn_intake_id", required=False, allow_null=True)
    paymentId = serializers.IntegerField(source="payment_id", required=False, allow_null=True)
    yarnName = serializers.CharField(source="yarn_name", required=False, allow_blank=True)
    yarnType = serializers.CharField(source="yarn_type", required=False, allow_blank=True)
    yarnCount = serializers.CharField(source="yarn_count", required=False, allow_blank=True)
    yarnQuality = serializers.CharField(source="yarn_quality", required=False, allow_blank=True)
    productionType = serializers.CharField(source="production_type", required=False, allow_blank=True)

    bagsIn = _ExactDecimalField(source="bags_in")
    conesIn = _ExactDecimalField(source="cones_in")
    weightKgIn = _ExactDecimalField(source="weight_kg_in")
    weightLbIn = _ExactDecimalField(source="weight_lb_in")
    ratePerLb = _ExactDecimalField(source="rate_per_lb")
    purchaseAmount = _ExactDecimalField(source="purchase_amount")

    paymentMethod = serializers.CharField(source="payment_method", required=False, allow_blank=True)
    referenceNumber = serializers.CharField(source="reference_number", required=False, allow_blank=True)
    bankAccountId = serializers.IntegerField(source="bank_account_id", required=False, allow_null=True)
    bankAccountName = serializers.CharField(source="bank_account_name", required=False, allow_blank=True)
    paymentAmount = _ExactDecimalField(source="payment_amount")

    amountPaid = _ExactDecimalField(source="amount_paid", required=False, allow_null=True)
    amountDue = _ExactDecimalField(source="amount_due", required=False, allow_null=True)
    paymentStatus = serializers.CharField(source="payment_status", required=False, allow_blank=True)

    remainingBags = _ExactDecimalField(source="remaining_bags", required=False, allow_null=True)
    remainingCones = _ExactDecimalField(source="remaining_cones", required=False, allow_null=True)
    remainingWeightKg = _ExactDecimalField(source="remaining_weight_kg", required=False, allow_null=True)
    remainingWeightLb = _ExactDecimalField(source="remaining_weight_lb", required=False, allow_null=True)
    dispatchedBags = _ExactDecimalField(source="dispatched_bags", required=False, allow_null=True)

    balanceBags = _ExactDecimalField(source="balance_bags")
    balanceCones = _ExactDecimalField(source="balance_cones")
    balanceWeightKg = _ExactDecimalField(source="balance_weight_kg")
    balanceWeightLb = _ExactDecimalField(source="balance_weight_lb")
    cumulativePurchases = _ExactDecimalField(source="cumulative_purchases")
    cumulativePaid = _ExactDecimalField(source="cumulative_paid")
    balancePayables = _ExactDecimalField(source="balance_payables")
    remarks = serializers.CharField(required=False, allow_blank=True)


class SupplierLedgerBalanceSerializer(serializers.Serializer):
    balanceBags = _ExactDecimalField(source="balance_bags")
    balanceCones = _ExactDecimalField(source="balance_cones")
    balanceWeightKg = _ExactDecimalField(source="balance_weight_kg")
    balanceWeightLb = _ExactDecimalField(source="balance_weight_lb")
    cumulativePurchases = _ExactDecimalField(source="cumulative_purchases")
    cumulativePaid = _ExactDecimalField(source="cumulative_paid")
    balancePayables = _ExactDecimalField(source="balance_payables")


class IndividualSupplierLedgerSummarySerializer(serializers.Serializer):
    totalBagsReceived = _ExactDecimalField(source="total_bags_received")
    totalConesReceived = _ExactDecimalField(source="total_cones_received")
    totalWeightKgReceived = _ExactDecimalField(source="total_weight_kg_received")
    totalWeightLbReceived = _ExactDecimalField(source="total_weight_lb_received")
    totalRemainingBags = _ExactDecimalField(source="total_remaining_bags")
    totalRemainingWeightKg = _ExactDecimalField(source="total_remaining_weight_kg")
    totalRemainingWeightLb = _ExactDecimalField(source="total_remaining_weight_lb")
    totalPurchases = _ExactDecimalField(source="total_purchases")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalPayables = _ExactDecimalField(source="total_payables")
    transactionsCount = serializers.IntegerField(source="transactions_count")


class MainSupplierLedgerItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    supplierId = serializers.IntegerField(source="supplier_id")
    supplierCode = serializers.CharField(source="supplier_code")
    supplierName = serializers.CharField(source="supplier_name")
    companyName = serializers.CharField(source="company_name", allow_blank=True)
    contactPerson = serializers.CharField(source="contact_person", allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    supplierType = serializers.CharField(source="supplier_type")

    totalBagsReceived = _ExactDecimalField(source="total_bags_received")
    totalConesReceived = _ExactDecimalField(source="total_cones_received")
    totalWeightKgReceived = _ExactDecimalField(source="total_weight_kg_received")
    totalWeightLbReceived = _ExactDecimalField(source="total_weight_lb_received")
    totalRemainingBags = _ExactDecimalField(source="total_remaining_bags")
    totalRemainingCones = _ExactDecimalField(source="total_remaining_cones")
    totalRemainingWeightKg = _ExactDecimalField(source="total_remaining_weight_kg")
    totalRemainingWeightLb = _ExactDecimalField(source="total_remaining_weight_lb")
    totalPurchases = _ExactDecimalField(source="total_purchases")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalPayables = _ExactDecimalField(source="total_payables")
    intakesCount = serializers.IntegerField(source="intakes_count")
    paymentsCount = serializers.IntegerField(source="payments_count")
    transactionsCount = serializers.IntegerField(source="transactions_count")


class MainSupplierLedgerSummarySerializer(serializers.Serializer):
    totalBagsReceived = _ExactDecimalField(source="total_bags_received")
    totalConesReceived = _ExactDecimalField(source="total_cones_received")
    totalWeightKgReceived = _ExactDecimalField(source="total_weight_kg_received")
    totalWeightLbReceived = _ExactDecimalField(source="total_weight_lb_received")
    totalRemainingBags = _ExactDecimalField(source="total_remaining_bags")
    totalRemainingCones = _ExactDecimalField(source="total_remaining_cones")
    totalRemainingWeightKg = _ExactDecimalField(source="total_remaining_weight_kg")
    totalRemainingWeightLb = _ExactDecimalField(source="total_remaining_weight_lb")
    totalPurchases = _ExactDecimalField(source="total_purchases")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalPayables = _ExactDecimalField(source="total_payables")
    suppliersCount = serializers.IntegerField(source="suppliers_count")
    intakesCount = serializers.IntegerField(source="intakes_count")
    paymentsCount = serializers.IntegerField(source="payments_count")
    transactionsCount = serializers.IntegerField(source="transactions_count")


class YarnSupplierPaymentSerializer(serializers.ModelSerializer):
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), required=False
    )
    supplierId = serializers.PrimaryKeyRelatedField(
        source="supplier", queryset=Supplier.objects.all(), required=False, write_only=True
    )
    supplierDetail = serializers.SerializerMethodField(read_only=True)
    yarn_intake = serializers.PrimaryKeyRelatedField(
        queryset=YarnIntake.objects.all(), required=False, allow_null=True
    )
    yarnIntakeId = serializers.PrimaryKeyRelatedField(
        source="yarn_intake", queryset=YarnIntake.objects.all(), required=False, allow_null=True, write_only=True
    )
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(), required=False, allow_null=True
    )
    bankAccountId = serializers.PrimaryKeyRelatedField(
        source="bank_account", queryset=BankAccount.objects.all(), required=False, allow_null=True, write_only=True
    )
    payment_date = serializers.DateField(required=False)
    paymentDate = serializers.DateField(source="payment_date", required=False, write_only=True)
    payment_method = serializers.CharField(required=False, allow_blank=True)
    paymentMethod = serializers.CharField(source="payment_method", required=False, allow_blank=True, write_only=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    referenceNumber = serializers.CharField(source="reference_number", required=False, allow_blank=True, write_only=True)

    class Meta:
        model = YarnSupplierPayment
        fields = [
            "id",
            "supplier",
            "supplierId",
            "supplierDetail",
            "yarn_intake",
            "yarnIntakeId",
            "bank_account",
            "bankAccountId",
            "amount",
            "payment_date",
            "paymentDate",
            "payment_method",
            "paymentMethod",
            "reference_number",
            "referenceNumber",
            "notes",
            "created_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "created_by"]

    def validate(self, attrs):
        if not attrs.get("supplier"):
            raise serializers.ValidationError({"supplier": "Supplier is required."})
        return attrs

    def get_supplierDetail(self, obj):
        if obj.supplier:
            return {
                "id": obj.supplier.id,
                "code": obj.supplier.supplier_code,
                "name": obj.supplier.supplier_name,
                "phone": obj.supplier.phone,
            }
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)
