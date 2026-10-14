"""
Read-only serializers for the Sizing Ledger.

Every numeric value is emitted as an EXACT plain-notation string. Ledger values
are derived (e.g. lagat_bags * weight_per_bag_kg), so a regular DRF DecimalField
would quantize them to `decimal_places` on output; `ExactDecimalField` never does.
"""

from rest_framework import serializers

from .ledger import exact_str


class ExactDecimalField(serializers.Field):
    """Serializes a Decimal as a full-precision string, with no quantization."""

    def to_representation(self, value):
        return exact_str(value)


class SizingLedgerRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    entryType = serializers.CharField(source="entry_type")
    date = serializers.DateField()

    sizingId = serializers.IntegerField(source="sizing_id")
    sizingName = serializers.CharField(source="sizing_name")
    reference = serializers.CharField()
    yarnOutcomeId = serializers.IntegerField(source="yarn_outcome_id", allow_null=True)
    sizingOutcomeId = serializers.IntegerField(source="sizing_outcome_id", allow_null=True)
    setNo = serializers.CharField(source="set_no")
    setBill = serializers.CharField(source="set_bill")

    # Income (yarn received by the sizing party)
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
    sizingCharge = ExactDecimalField(source="sizing_charge")

    # Running balances (per sizing party)
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
    totalWeightLbOut = ExactDecimalField(source="total_weight_lb_out")
    totalSizingCharge = ExactDecimalField(source="total_sizing_charge")


class SizingLedgerPartySummarySerializer(_SummaryBlockSerializer):
    sizingId = serializers.IntegerField(source="sizing_id")
    sizingName = serializers.CharField(source="sizing_name")


class SizingLedgerTotalsSerializer(_SummaryBlockSerializer):
    pass
