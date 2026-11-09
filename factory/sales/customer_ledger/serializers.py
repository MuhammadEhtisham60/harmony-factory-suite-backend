"""
DRF Serializers for Customer Cloth Ledger and Cloth Sales.
"""

from decimal import Decimal
from rest_framework import serializers

from factory.sales.customer.models import Customer
from factory.cloth.models import ClothName
from factory.bank_account.models import BankAccount
from .models import ClothSale, ClothCustomerPayment
from .ledger import exact_str


class _ExactDecimalField(serializers.Field):
    """Serializes Decimal to plain string notation without scientific notation."""

    def to_representation(self, value):
        if value is None:
            return "0"
        return exact_str(value)


class ClothSaleSerializer(serializers.ModelSerializer):
    customerName = serializers.CharField(source="customer.customer_name", read_only=True)
    customerCode = serializers.CharField(source="customer.customer_code", read_only=True)
    clothQuality = serializers.CharField(source="cloth_name.name", read_only=True)

    quantityMeters = serializers.DecimalField(source="quantity_meters", max_digits=15, decimal_places=4, required=False, write_only=True)
    quantity_meters = serializers.DecimalField(max_digits=15, decimal_places=4, required=False)
    ratePerMeter = serializers.DecimalField(source="rate_per_meter", max_digits=15, decimal_places=4, required=False, write_only=True)
    rate_per_meter = serializers.DecimalField(max_digits=15, decimal_places=4, required=False)

    totalAmount = _ExactDecimalField(source="total_amount", read_only=True)
    amountPaid = _ExactDecimalField(source="amount_paid", read_only=True)
    amountDue = _ExactDecimalField(source="amount_due", read_only=True)
    paymentStatus = serializers.CharField(source="payment_status", read_only=True)

    saleDate = serializers.DateField(source="sale_date", required=False, write_only=True)
    sale_date = serializers.DateField(required=False)
    invoiceNumber = serializers.CharField(source="invoice_number", read_only=True)

    deliveryChallanNo = serializers.CharField(source="delivery_challan_no", required=False, allow_blank=True, write_only=True)
    delivery_challan_no = serializers.CharField(required=False, allow_blank=True)
    vehicleNo = serializers.CharField(source="vehicle_no", required=False, allow_blank=True, write_only=True)
    vehicle_no = serializers.CharField(required=False, allow_blank=True)
    driverName = serializers.CharField(source="driver_name", required=False, allow_blank=True, write_only=True)
    driver_name = serializers.CharField(required=False, allow_blank=True)
    deductFromStock = serializers.BooleanField(source="deduct_from_stock", required=False, write_only=True)
    deduct_from_stock = serializers.BooleanField(required=False)

    customerId = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.all(),
        required=False,
        write_only=True
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        required=False
    )
    clothNameId = serializers.PrimaryKeyRelatedField(
        source="cloth_name",
        queryset=ClothName.objects.all(),
        required=False,
        write_only=True
    )
    cloth_name = serializers.PrimaryKeyRelatedField(
        queryset=ClothName.objects.all(),
        required=False
    )

    class Meta:
        model = ClothSale
        fields = [
            "id",
            "invoiceNumber",
            "invoice_number",
            "customerId",
            "customer",
            "customerName",
            "customerCode",
            "clothNameId",
            "cloth_name",
            "clothQuality",
            "saleDate",
            "sale_date",
            "quantityMeters",
            "quantity_meters",
            "ratePerMeter",
            "rate_per_meter",
            "totalAmount",
            "total_amount",
            "amountPaid",
            "amount_paid",
            "amountDue",
            "amount_due",
            "paymentStatus",
            "payment_status",
            "status",
            "deliveryChallanNo",
            "delivery_challan_no",
            "vehicleNo",
            "vehicle_no",
            "driverName",
            "driver_name",
            "deductFromStock",
            "deduct_from_stock",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invoiceNumber",
            "invoice_number",
            "totalAmount",
            "total_amount",
            "amountPaid",
            "amount_paid",
            "amountDue",
            "amount_due",
            "paymentStatus",
            "payment_status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if not attrs.get("customer"):
            raise serializers.ValidationError({"customer": "Customer is required."})
        if not attrs.get("cloth_name"):
            raise serializers.ValidationError({"cloth_name": "Cloth Name is required."})
        if not attrs.get("quantity_meters") or Decimal(str(attrs.get("quantity_meters"))) <= Decimal("0.00"):
            raise serializers.ValidationError({"quantity_meters": "Quantity in meters must be greater than zero."})
        if not attrs.get("rate_per_meter") or Decimal(str(attrs.get("rate_per_meter"))) <= Decimal("0.00"):
            raise serializers.ValidationError({"rate_per_meter": "Rate per meter must be greater than zero."})
        return attrs


class ClothCustomerPaymentSerializer(serializers.ModelSerializer):
    customerName = serializers.CharField(source="customer.customer_name", read_only=True)
    customerCode = serializers.CharField(source="customer.customer_code", read_only=True)
    bankAccountName = serializers.CharField(source="bank_account.bank_name", read_only=True, default="")
    clothSaleInvoice = serializers.CharField(source="cloth_sale.invoice_number", read_only=True, default="")

    paymentNumber = serializers.CharField(source="payment_number", read_only=True)
    paymentDate = serializers.DateField(source="payment_date", required=False, write_only=True)
    payment_date = serializers.DateField(required=False)
    paymentMethod = serializers.CharField(source="payment_method", required=False, write_only=True)
    payment_method = serializers.CharField(required=False)
    referenceNumber = serializers.CharField(source="reference_number", required=False, allow_blank=True, write_only=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)

    customerId = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.all(),
        required=False,
        write_only=True
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        required=False
    )
    clothSaleId = serializers.PrimaryKeyRelatedField(
        source="cloth_sale",
        queryset=ClothSale.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    cloth_sale = serializers.PrimaryKeyRelatedField(
        queryset=ClothSale.objects.all(),
        required=False,
        allow_null=True
    )
    bankAccountId = serializers.PrimaryKeyRelatedField(
        source="bank_account",
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = ClothCustomerPayment
        fields = [
            "id",
            "paymentNumber",
            "payment_number",
            "customerId",
            "customer",
            "customerName",
            "customerCode",
            "clothSaleId",
            "cloth_sale",
            "clothSaleInvoice",
            "bankAccountId",
            "bank_account",
            "bankAccountName",
            "amount",
            "paymentDate",
            "payment_date",
            "paymentMethod",
            "payment_method",
            "referenceNumber",
            "reference_number",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "paymentNumber",
            "payment_number",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if not attrs.get("customer"):
            raise serializers.ValidationError({"customer": "Customer is required."})
        if not attrs.get("amount") or Decimal(str(attrs.get("amount"))) <= Decimal("0.00"):
            raise serializers.ValidationError({"amount": "Payment amount must be greater than zero."})
        return attrs


class CustomerLedgerRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    entryType = serializers.CharField(source="entry_type")
    entry_type = serializers.CharField()
    date = serializers.DateField()
    customerId = serializers.IntegerField(source="customer_id")
    customer_id = serializers.IntegerField()
    customerCode = serializers.CharField(source="customer_code")
    customerName = serializers.CharField(source="customer_name")
    reference = serializers.CharField()

    clothSaleId = serializers.IntegerField(source="cloth_sale_id", required=False, allow_null=True)
    paymentId = serializers.IntegerField(source="payment_id", required=False, allow_null=True)
    invoiceNumber = serializers.CharField(source="invoice_number", required=False, allow_blank=True)
    clothNameId = serializers.IntegerField(source="cloth_name_id", required=False, allow_null=True)
    clothQuality = serializers.CharField(source="cloth_quality", required=False, allow_blank=True)

    quantityMeters = _ExactDecimalField(source="quantity_meters")
    ratePerMeter = _ExactDecimalField(source="rate_per_meter")
    saleAmount = _ExactDecimalField(source="sale_amount")

    paymentMethod = serializers.CharField(source="payment_method", required=False, allow_blank=True)
    referenceNumber = serializers.CharField(source="reference_number", required=False, allow_blank=True)
    bankAccountId = serializers.IntegerField(source="bank_account_id", required=False, allow_null=True)
    bankAccountName = serializers.CharField(source="bank_account_name", required=False, allow_blank=True)
    paymentAmount = _ExactDecimalField(source="payment_amount")

    amountPaid = _ExactDecimalField(source="amount_paid", required=False, allow_null=True)
    amountDue = _ExactDecimalField(source="amount_due", required=False, allow_null=True)
    paymentStatus = serializers.CharField(source="payment_status", required=False, allow_blank=True)
    deliveryChallanNo = serializers.CharField(source="delivery_challan_no", required=False, allow_blank=True)
    vehicleNo = serializers.CharField(source="vehicle_no", required=False, allow_blank=True)
    driverName = serializers.CharField(source="driver_name", required=False, allow_blank=True)

    balanceMeters = _ExactDecimalField(source="balance_meters")
    cumulativeSales = _ExactDecimalField(source="cumulative_sales")
    cumulativePaid = _ExactDecimalField(source="cumulative_paid")
    balanceReceivables = _ExactDecimalField(source="balance_receivables")
    remarks = serializers.CharField(required=False, allow_blank=True)


class CustomerLedgerBalanceSerializer(serializers.Serializer):
    balanceMeters = _ExactDecimalField(source="balance_meters")
    cumulativeSales = _ExactDecimalField(source="cumulative_sales")
    cumulativePaid = _ExactDecimalField(source="cumulative_paid")
    balanceReceivables = _ExactDecimalField(source="balance_receivables")


class IndividualCustomerLedgerSummarySerializer(serializers.Serializer):
    totalMetersSold = _ExactDecimalField(source="total_meters_sold")
    totalSales = _ExactDecimalField(source="total_sales")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalReceivables = _ExactDecimalField(source="total_receivables")
    salesCount = serializers.IntegerField(source="sales_count")
    paymentsCount = serializers.IntegerField(source="payments_count")
    transactionsCount = serializers.IntegerField(source="transactions_count")


class MainCustomerLedgerItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    customerId = serializers.IntegerField(source="customer_id")
    customerCode = serializers.CharField(source="customer_code")
    customerName = serializers.CharField(source="customer_name")
    companyName = serializers.CharField(source="company_name", allow_blank=True)
    contactPerson = serializers.CharField(source="contact_person", allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)
    customerType = serializers.CharField(source="customer_type")
    status = serializers.CharField()

    totalMetersSold = _ExactDecimalField(source="total_meters_sold")
    totalSales = _ExactDecimalField(source="total_sales")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalReceivables = _ExactDecimalField(source="total_receivables")
    salesCount = serializers.IntegerField(source="sales_count")
    paymentsCount = serializers.IntegerField(source="payments_count")
    transactionsCount = serializers.IntegerField(source="transactions_count")


class MainCustomerLedgerSummarySerializer(serializers.Serializer):
    totalCustomers = serializers.IntegerField(source="total_customers")
    activeCustomers = serializers.IntegerField(source="active_customers")
    totalMetersSold = _ExactDecimalField(source="total_meters_sold")
    totalSales = _ExactDecimalField(source="total_sales")
    totalPaid = _ExactDecimalField(source="total_paid")
    totalReceivables = _ExactDecimalField(source="total_receivables")
