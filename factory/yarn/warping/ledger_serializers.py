"""
Read-only serializers for the Warping Ledger.
"""

from rest_framework import serializers
from .ledger import exact_str


class ExactDecimalField(serializers.Field):
    """Serializes a Decimal as a full-precision string, with no quantization."""

    def to_representation(self, value):
        return exact_str(value)


class WarpingLedgerRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    entryType = serializers.CharField(source="entry_type")
    date = serializers.DateField()

    warpingId = serializers.IntegerField(source="warping_id")
    warpingName = serializers.CharField(source="warping_name")
    reference = serializers.CharField()
    yarnOutcomeId = serializers.IntegerField(source="yarn_outcome_id", allow_null=True)
    sizingOutcomeId = serializers.IntegerField(source="sizing_outcome_id", allow_null=True)
    warpingOutcomeId = serializers.IntegerField(source="warping_outcome_id", allow_null=True, required=False)
    setNo = serializers.CharField(source="set_no")
    setBill = serializers.CharField(source="set_bill")

    # Income (yarn received by the warping party)
    bagsIn = ExactDecimalField(source="bags_in")
    conesIn = ExactDecimalField(source="cones_in")
    weightKgIn = ExactDecimalField(source="weight_kg_in")
    weightLbIn = ExactDecimalField(source="weight_lb_in")

    # Outcome (set returned / yarn consumed)
    bagsOut = ExactDecimalField(source="bags_out")
    conesOut = ExactDecimalField(source="cones_out")
    weightKgOut = ExactDecimalField(source="weight_kg_out")
    weightLbOut = ExactDecimalField(source="weight_lb_out")
    setLengthMeter = ExactDecimalField(source="set_length_meter")
    setLengthGaz = ExactDecimalField(source="set_length_gaz")
    shortage = ExactDecimalField()
    netWeightKg = ExactDecimalField(source="net_weight_kg")
    ratePerKg = ExactDecimalField(source="rate_per_kg")
    warpingCharge = ExactDecimalField(source="warping_charge")
    amountPaid = ExactDecimalField(source="amount_paid", required=False, allow_null=True)
    amountDue = ExactDecimalField(source="amount_due", required=False, allow_null=True)
    paymentStatus = serializers.CharField(source="payment_status", required=False, allow_null=True)

    # Running balances (per warping party)
    balanceBags = ExactDecimalField(source="balance_bags")
    balanceCones = ExactDecimalField(source="balance_cones")
    balanceWeightKg = ExactDecimalField(source="balance_weight_kg")
    balanceWeightLb = ExactDecimalField(source="balance_weight_lb")
    chargesPayable = ExactDecimalField(source="charges_payable")

    remarks = serializers.CharField()


class BalanceSerializer(serializers.Serializer):
    balanceBags = ExactDecimalField(source="balance_bags")
    balanceCones = ExactDecimalField(source="balance_cones")
    balanceWeightKg = ExactDecimalField(source="balance_weight_kg")
    balanceWeightLb = ExactDecimalField(source="balance_weight_lb")
    chargesPayable = ExactDecimalField(source="charges_payable")


class _SummaryBlockSerializer(BalanceSerializer):
    entries = serializers.IntegerField()
    totalBagsIn = ExactDecimalField(source="total_bags_in")
    totalConesIn = ExactDecimalField(source="total_cones_in")
    totalWeightKgIn = ExactDecimalField(source="total_weight_kg_in")
    totalWeightLbIn = ExactDecimalField(source="total_weight_lb_in")
    totalBagsOut = ExactDecimalField(source="total_bags_out")
    totalConesOut = ExactDecimalField(source="total_cones_out")
    totalWeightKgOut = ExactDecimalField(source="total_weight_kg_out")
    totalWarpingCharge = ExactDecimalField(source="total_warping_charge")
    totalAmountPaid = ExactDecimalField(source="total_amount_paid", required=False)
    totalPayables = ExactDecimalField(source="total_payables", required=False)


class WarpingLedgerPartySummarySerializer(_SummaryBlockSerializer):
    warpingId = serializers.IntegerField(source="warping_id")
    warpingName = serializers.CharField(source="warping_name")


class WarpingLedgerTotalsSerializer(_SummaryBlockSerializer):
    pass


class MainWarpingLedgerItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    warpingName = serializers.CharField(source="warping_name")
    contactPerson = serializers.CharField(source="contact_person", allow_blank=True)
    contactNumber = serializers.CharField(source="phone_no", allow_blank=True)
    phoneNo = serializers.CharField(source="phone_no", allow_blank=True)
    email = serializers.EmailField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    notes = serializers.CharField(allow_blank=True)

    totalBoxesSent = ExactDecimalField(source="total_boxes_sent")
    totalBoxesReceived = ExactDecimalField(source="total_boxes_received")
    totalBoxesBalance = ExactDecimalField(source="total_boxes_balance")
    totalPayables = ExactDecimalField(source="total_payables")
    totalPaid = ExactDecimalField(source="total_paid", required=False)
    totalCharges = ExactDecimalField(source="total_charges", required=False)

    totalWeightKgSent = ExactDecimalField(source="total_weight_kg_sent")
    totalWeightKgReceived = ExactDecimalField(source="total_weight_kg_received")
    totalWeightKgBalance = ExactDecimalField(source="total_weight_kg_balance")

    totalConesSent = ExactDecimalField(source="total_cones_sent")
    totalConesReceived = ExactDecimalField(source="total_cones_received")
    totalConesBalance = ExactDecimalField(source="total_cones_balance")

    transactionsCount = serializers.IntegerField(source="transactions_count")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")


class MainWarpingLedgerSummarySerializer(serializers.Serializer):
    totalPayables = ExactDecimalField(source="total_payables")
    totalPaid = ExactDecimalField(source="total_paid", required=False)
    totalCharges = ExactDecimalField(source="total_charges", required=False)
    totalBoxesSent = ExactDecimalField(source="total_boxes_sent")
    totalBoxesReceived = ExactDecimalField(source="total_boxes_received")
    totalBoxesBalance = ExactDecimalField(source="total_boxes_balance")

    totalWeightKgSent = ExactDecimalField(source="total_weight_kg_sent")
    totalWeightKgReceived = ExactDecimalField(source="total_weight_kg_received")
    totalWeightKgBalance = ExactDecimalField(source="total_weight_kg_balance")

    totalConesSent = ExactDecimalField(source="total_cones_sent")
    totalConesReceived = ExactDecimalField(source="total_cones_received")
    totalConesBalance = ExactDecimalField(source="total_cones_balance")
    totalWarpingsCount = serializers.IntegerField(source="total_warpings_count")


class WarpingDetailSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    warpingName = serializers.CharField(source="warping_name")
    contactPerson = serializers.CharField(source="contact_person", allow_blank=True)
    contactNumber = serializers.CharField(source="phone_no", allow_blank=True)
    phoneNo = serializers.CharField(source="phone_no", allow_blank=True)
    email = serializers.EmailField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    notes = serializers.CharField(allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")


class IndividualWarpingSummarySerializer(serializers.Serializer):
    totalPayables = ExactDecimalField(source="total_payables")
    totalPaid = ExactDecimalField(source="total_paid", required=False)
    totalCharges = ExactDecimalField(source="total_charges", required=False)
    totalBoxesSent = ExactDecimalField(source="total_boxes_sent")
    totalBoxesReceived = ExactDecimalField(source="total_boxes_received")
    totalBoxesBalance = ExactDecimalField(source="total_boxes_balance")

    totalWeightKgSent = ExactDecimalField(source="total_weight_kg_sent")
    totalWeightKgReceived = ExactDecimalField(source="total_weight_kg_received")
    totalWeightKgBalance = ExactDecimalField(source="total_weight_kg_balance")

    totalConesSent = ExactDecimalField(source="total_cones_sent")
    totalConesReceived = ExactDecimalField(source="total_cones_received")
    totalConesBalance = ExactDecimalField(source="total_cones_balance")
